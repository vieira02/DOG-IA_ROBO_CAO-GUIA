"""DOG-IA v2 - Robô cão-guia urbano (AC-4).

Uso:
    python dog_ia_v2.py                         # simulador com janela
    python dog_ia_v2.py --benchmark 20 --seed 1 # sem janela, imprime métricas
"""
import argparse
import heapq
import math
import os
import random
import statistics
import sys
from array import array
from collections import deque

if "--benchmark" in sys.argv:  # execução headless: sem janela nem áudio
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

# ==================== CONSTANTES ====================
LARGURA, ALTURA, FPS = 1050, 680, 60
AREA = LARGURA - 260                 # largura do mapa (o resto é o painel)
RUA_Y, RUA_H = 250, 170
RUA_FIM = RUA_Y + RUA_H
FAIXA_X, FAIXA_W = 580, 95
VEL = 156.0                          # px/s do robô
GUIA = 42                            # comprimento do arnês (px)
FOLGA_ARNES = 10                     # tensão acima disso reduz a velocidade
TUTOR_VEL = 165.0
PX_M = 0.05                          # 1 px = 0,05 m

# Semáforo (tempo simulado em segundos)
FASES = [("VERDE", 6.0), ("AMARELO", 2.0), ("TODOS_VERM_1", 1.5),
         ("PEDESTRE", 7.0), ("TODOS_VERM_2", 1.5)]
CICLO = sum(d for _, d in FASES)

# Veículos
ACEL, DESACEL, VEL_CARRO, DIST_SEG = 90.0, 180.0, 130.0, 28.0

# Planejamento global
CELULA = 10
INFLA = {"solo": 30, "edificio": 22, "suspenso": 38}
CUSTO_TATIL = 0.45
TEMPO_PRESO = 3.5

# LiDAR
ALCANCE, N_RAIOS, FOV = 165, 19, math.radians(150)
SIGMA, DROPOUT = 1.5, 0.02

DESTINOS = {1: ("MERCADO", (100, 545)), 2: ("FARMÁCIA", (700, 125)),
            3: ("PADARIA", (700, 545)), 4: ("CASA", (100, 125))}
TATIL = [pygame.Rect(40, 120, 690, 14), pygame.Rect(621, 120, 14, 130),
         pygame.Rect(621, RUA_FIM, 14, 130), pygame.Rect(60, 536, 670, 14)]

BRANCO, PRETO = (245, 245, 245), (20, 22, 28)
ASFALTO, CALCADA, MEIO_FIO = (42, 45, 52), (130, 134, 142), (175, 180, 188)
PISO_TATIL, GRAMA = (235, 190, 20), (46, 115, 65)
AZUL, AZUL_ESC = (30, 136, 229), (15, 76, 129)
VERDE, LARANJA, VERMELHO, ROXO = (46, 204, 113), (255, 140, 0), (225, 55, 55), (155, 89, 182)


def norma(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def limite_travessia():
    """Tempo mínimo restante de PEDESTRE para iniciar a travessia."""
    return (RUA_H + 24 + GUIA) / VEL * 1.35 + 0.4


# ==================== MARCO 1: SEMÁFORO E VEÍCULOS ====================
class Semaforo:
    def __init__(self, t=0.0):
        self.t = t % CICLO

    def update(self, dt):
        self.t = (self.t + dt) % CICLO

    def estado(self):
        """(nome da fase, segundos restantes na fase)."""
        acc = 0.0
        for nome, dur in FASES:
            if self.t < acc + dur:
                return nome, acc + dur - self.t
            acc += dur
        return FASES[0][0], FASES[0][1]


class Carro:
    W, H = 54, 28

    def __init__(self, sentido, infrator, rng):
        self.s = sentido
        self.x = -40.0 if sentido > 0 else AREA + 40.0
        self.y = RUA_Y + (43 if sentido > 0 else 127)
        self.infrator = infrator
        self.vmax = VEL_CARRO * (1.15 if infrator else 1.0)
        self.v = self.vmax
        self.passa = None            # decidiu atravessar no amarelo?
        self.bateu = self.quase = False
        self.cor = (255, 90, 0) if infrator else rng.choice([(215, 50, 50), (240, 170, 20), (235, 235, 235)])

    @property
    def rect(self):
        return pygame.Rect(self.x - self.W / 2, self.y - self.H / 2, self.W, self.H)

    def update(self, dt, fase, lider):
        alvo = self.vmax
        if lider is not None:                       # distância de seguimento
            gap = (lider.x - self.x) * self.s - self.W
            alvo = min(alvo, math.sqrt(2 * DESACEL * max(gap - DIST_SEG, 0)))
        if fase != "VERDE" and not self.infrator:   # linha de retenção da faixa
            linha = FAIXA_X - 14 if self.s > 0 else FAIXA_X + FAIXA_W + 14
            d = (linha - (self.x + self.s * self.W / 2)) * self.s
            if self.passa is None:                  # decide uma vez: dá para parar?
                self.passa = d < self.v ** 2 / (2 * DESACEL)
            if not self.passa and d >= 0:
                alvo = min(alvo, math.sqrt(2 * DESACEL * max(d - 2, 0)))
        else:
            self.passa = None
        if self.v > alvo:
            self.v = max(alvo, self.v - DESACEL * dt)
        else:
            self.v = min(alvo, self.v + ACEL * dt)
        self.x += self.s * self.v * dt


# ==================== MARCO 2: A* EM GRADE ====================
COLS, LINS = AREA // CELULA, ALTURA // CELULA


def criar_cenario():
    def o(x, y, w, h, tipo, nome, cor):
        return {"rect": pygame.Rect(x, y, w, h), "tipo": tipo, "nome": nome, "cor": cor}
    return [
        o(40, 36, 110, 56, "edificio", "CASA", (50, 120, 190)),
        o(650, 36, 110, 56, "edificio", "FARMÁCIA", (225, 70, 125)),
        o(40, 588, 110, 48, "edificio", "MERCADO", (30, 165, 145)),
        o(650, 588, 110, 48, "edificio", "PADARIA", (235, 145, 55)),
        o(260, 70, 70, 44, "solo", "OBSTÁCULO", (95, 100, 110)),
        o(430, 108, 48, 40, "solo", "LIXEIRA", (46, 160, 110)),
        o(290, 470, 70, 50, "suspenso", "ALTO", ROXO),
        o(480, 510, 70, 45, "solo", "OBSTÁCULO", (95, 100, 110)),
    ]


def montar_grade(obst):
    """Grade de ocupação com C-Space (inflação por tipo) e custo reduzido no piso tátil."""
    bloq = [[False] * COLS for _ in range(LINS)]
    custo = [[1.0] * COLS for _ in range(LINS)]
    infladas = [(o["rect"].inflate(2 * INFLA[o["tipo"]], 2 * INFLA[o["tipo"]])) for o in obst]
    for j in range(LINS):
        for i in range(COLS):
            x, y = i * CELULA + CELULA // 2, j * CELULA + CELULA // 2
            if x < 25 or x > AREA - 25 or y < 48 or y > ALTURA - 48:
                bloq[j][i] = True
            elif RUA_Y - 10 <= y < RUA_FIM + 10 and not (FAIXA_X + 35 <= x <= FAIXA_X + 60):
                bloq[j][i] = True       # meio-fio: só a faixa é transitável
            elif any(r.collidepoint(x, y) for r in infladas):
                bloq[j][i] = True
            elif any(r.collidepoint(x, y) for r in TATIL):
                custo[j][i] = CUSTO_TATIL
    return bloq, custo


def celula_livre(bloq, x, y):
    i0, j0 = min(COLS - 1, max(0, int(x // CELULA))), min(LINS - 1, max(0, int(y // CELULA)))
    for r in range(0, 12):
        melhor = None
        for j in range(max(0, j0 - r), min(LINS, j0 + r + 1)):
            for i in range(max(0, i0 - r), min(COLS, i0 + r + 1)):
                if not bloq[j][i]:
                    d = (i - i0) ** 2 + (j - j0) ** 2
                    if melhor is None or d < melhor[0]:
                        melhor = (d, i, j)
        if melhor:
            return melhor[1], melhor[2]
    return None


def astar(grade, ini, fim):
    """A* 8-vizinhos com heurística octile. Retorna lista de (x, y) ou None."""
    bloq, custo = grade
    a, b = celula_livre(bloq, *ini), celula_livre(bloq, *fim)
    if a is None or b is None:
        return None
    s2 = math.sqrt(2)

    def h(c):
        dx, dy = abs(c[0] - b[0]), abs(c[1] - b[1])
        return CELULA * CUSTO_TATIL * (dx + dy + (s2 - 2) * min(dx, dy))   # admissível

    g, pai, aberto = {a: 0.0}, {}, [(h(a), a)]
    while aberto:
        _, c = heapq.heappop(aberto)
        if c == b:
            caminho = [c]
            while c in pai:
                c = pai[c]
                caminho.append(c)
            return [(i * CELULA + CELULA // 2, j * CELULA + CELULA // 2) for i, j in reversed(caminho)]
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                n = (c[0] + di, c[1] + dj)
                if (di == 0 and dj == 0) or not (0 <= n[0] < COLS and 0 <= n[1] < LINS) or bloq[n[1]][n[0]]:
                    continue
                if di and dj and (bloq[c[1]][n[0]] or bloq[n[1]][c[0]]):
                    continue                                  # sem cortar quina
                passo = CELULA * (s2 if di and dj else 1) * (custo[c[1]][c[0]] + custo[n[1]][n[0]]) / 2
                if g[c] + passo < g.get(n, 1e18):
                    g[n], pai[n] = g[c] + passo, c
                    heapq.heappush(aberto, (g[n] + h(n), n))
    return None


# ==================== MARCO 3: LIDAR ====================
class Robo:
    def __init__(self, x, y):
        self.x, self.y, self.angulo = float(x), float(y), 0.0
        self.px, self.py = self.x, self.y
        self.janela = [deque(maxlen=3) for _ in range(N_RAIOS)]
        self.leituras = []
        self.passo_anim = 0.0

    def caixa(self):
        return pygame.Rect(self.x - 16, self.y - 16, 32, 32)

    def ler_lidar(self, alvos, rng):
        """Interseção analítica (clipline) + ruído gaussiano + dropout + mediana de 3 varreduras."""
        perto = [(r, t) for r, t in alvos
                 if r.colliderect(pygame.Rect(self.x - ALCANCE, self.y - ALCANCE, 2 * ALCANCE, 2 * ALCANCE))]
        self.leituras = []
        for i in range(N_RAIOS):
            ang = self.angulo - FOV / 2 + i * FOV / (N_RAIOS - 1)
            x1, y1 = self.x + math.cos(ang) * ALCANCE, self.y + math.sin(ang) * ALCANCE
            leitura = (float(ALCANCE), None)
            if rng.random() >= DROPOUT:                    # dropout: devolve alcance máximo
                for r, t in perto:
                    c = r.clipline(self.x, self.y, x1, y1)
                    if c:
                        d = math.hypot(c[0][0] - self.x, c[0][1] - self.y)
                        if d < leitura[0]:
                            leitura = (d, t)
                if leitura[1]:
                    leitura = (max(0.0, min(ALCANCE, leitura[0] + rng.gauss(0, SIGMA))), leitura[1])
            self.janela[i].append(leitura)
            d, t = sorted(self.janela[i], key=lambda e: e[0])[len(self.janela[i]) // 2]
            self.leituras.append({"angulo": ang, "distancia": d, "tipo": t if d < ALCANCE else None})

    def desenhar(self, tela, tutor):
        for r in self.leituras:
            fx, fy = self.x + math.cos(r["angulo"]) * r["distancia"], self.y + math.sin(r["angulo"]) * r["distancia"]
            pygame.draw.line(tela, VERDE if r["distancia"] >= ALCANCE - 5 else VERMELHO, (self.x, self.y), (fx, fy), 1)
            if r["tipo"]:
                pygame.draw.circle(tela, BRANCO, (int(fx), int(fy)), 3)
        pygame.draw.line(tela, (255, 215, 0), (self.x, self.y), (tutor.x, tutor.y), 4)
        pygame.draw.circle(tela, (235, 235, 240), (int(tutor.x), int(tutor.y)), 12)
        pygame.draw.circle(tela, PRETO, (int(tutor.x), int(tutor.y)), 12, 2)

        def rot(ox, oy):
            s, c = math.sin(self.angulo), math.cos(self.angulo)
            return (int(self.x + ox * c - oy * s), int(self.y + ox * s + oy * c))
        bal = math.sin(self.passo_anim) * 5
        for ox, oy in [(10 + bal, -14), (10 - bal, 14), (-12 - bal, -14), (-12 + bal, 14)]:
            pygame.draw.circle(tela, AZUL_ESC, rot(ox, oy), 5)
        corpo = [rot(16, -11), rot(16, 11), rot(-18, 11), rot(-18, -11)]
        pygame.draw.polygon(tela, AZUL, corpo)
        pygame.draw.polygon(tela, BRANCO, corpo, 2)
        pygame.draw.circle(tela, (230, 236, 245), rot(21, 0), 9)
        pygame.draw.circle(tela, AZUL_ESC, rot(21, 0), 9, 2)
        pygame.draw.circle(tela, AZUL_ESC, rot(19, -10), 4)
        pygame.draw.circle(tela, AZUL_ESC, rot(19, 10), 4)
        pygame.draw.circle(tela, LARANJA, rot(3, 0), 5)


class Tutor:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)

    def caixa(self):
        return pygame.Rect(self.x - 10, self.y - 10, 20, 20)


# ==================== MUNDO: MÁQUINA DE ESTADOS + MARCO 4 ====================
class Mundo:
    def __init__(self, rng, inicio=4, destino=1, p_infrator=0.0):
        self.rng, self.p_infrator = rng, p_infrator
        self.sinal = Semaforo(rng.uniform(0, CICLO))
        self.carros, self.t_spawn = [], {1: 0.0, -1: rng.uniform(0, 2)}
        self.obst = criar_cenario()
        self.paredes = [(pygame.Rect(-20, -20, AREA + 40, 35), "parede"), (pygame.Rect(-20, ALTURA - 15, AREA + 40, 35), "parede"),
                        (pygame.Rect(-20, -20, 35, ALTURA + 40), "parede"), (pygame.Rect(AREA - 15, -20, 35, ALTURA + 40), "parede")]
        x, y = DESTINOS[inicio][1]
        self.robo, self.tutor = Robo(x, y), Tutor(x - GUIA, y)
        self.autonomo, self.pausa, self.viagens = True, False, 0
        self.bips, self.t_bip, self.tensao = [], 0.0, 0.0
        self.fase_ant = None
        self.regrade()
        self.nova_viagem(*DESTINOS[destino])
        for _ in range(int(6 * FPS)):                      # aquece o trânsito
            self.sinal.update(1 / FPS)
            self._carros(1 / FPS)

    # ---- viagem / planejamento ----
    def regrade(self):
        self.grade = montar_grade(self.obst)

    def replanejar(self):
        self.path = astar(self.grade, (self.robo.x, self.robo.y), self.dest_pos)
        self.idx = 0
        self.ref_preso, self.t_preso = (self.robo.x, self.robo.y), 0.0

    def nova_viagem(self, nome, pos):
        self.dest_nome, self.dest_pos = nome, pos
        self.m = dict(t=0.0, dist=0.0, alertas=0, freios=0, quase=0, col=0, sinal_fechou=0)
        self.cruzando, self.estado, self.estado_ant, self.t_livre = False, "NAVEGANDO", "NAVEGANDO", 0.0
        self.alerta_prev = False
        self.status, self.cor = f"Guiando até {nome}.", VERDE
        for c in self.carros:
            c.bateu = c.quase = False
        self.replanejar()

    # ---- carros ----
    def _carros(self, dt):
        for s in (1, -1):
            self.t_spawn[s] -= dt
            if self.t_spawn[s] <= 0:
                self.t_spawn[s] = self.rng.uniform(2.0, 4.5)
                x0 = -40 if s > 0 else AREA + 40
                if all(abs(c.x - x0) > 120 for c in self.carros if c.s == s):
                    self.carros.append(Carro(s, self.rng.random() < self.p_infrator, self.rng))
        fase = self.sinal.estado()[0]
        for c in self.carros:
            na_frente = [o for o in self.carros if o is not c and o.s == c.s and (o.x - c.x) * c.s > 0]
            c.update(dt, fase, min(na_frente, key=lambda o: abs(o.x - c.x)) if na_frente else None)
        self.carros = [c for c in self.carros if -80 < c.x < AREA + 80]

    def infrator(self):
        c = Carro(self.rng.choice([1, -1]), True, self.rng)
        self.carros.append(c)

    # ---- segurança ----
    def _perigo(self):
        """Zona varrida: projeta cada carro em movimento 1,0 s à frente."""
        caixas = [self.robo.caixa().inflate(8, 8), self.tutor.caixa().inflate(8, 8)]
        for c in self.carros:
            if c.v < 8:
                continue
            varrida = c.rect.union(c.rect.move(c.s * c.v * 1.0, 0))
            if any(varrida.colliderect(b) for b in caixas):
                return True
        return False

    def _autorizado(self):
        nome, resta = self.sinal.estado()
        if nome != "PEDESTRE" or resta <= limite_travessia():
            return False
        zona = pygame.Rect(FAIXA_X - 10, RUA_Y, FAIXA_W + 20, RUA_H)
        return not any(c.v > 15 and c.rect.union(c.rect.move(c.s * c.v * 2.5, 0)).colliderect(zona) for c in self.carros)

    def aplicar_barreira(self):
        """Impede descer o meio-fio fora da faixa ou sem travessia autorizada."""
        r = self.robo
        if RUA_Y - 2 < r.y < RUA_FIM + 2:
            na_faixa = FAIXA_X + 15 <= r.x <= FAIXA_X + FAIXA_W - 15
            liberado = self.cruzando or (not self.autonomo and self.sinal.estado()[0] == "PEDESTRE")
            if not (na_faixa and liberado):
                r.x, r.y = r.px, r.py

    def _contagem_colisoes(self):
        caixas = [self.robo.caixa(), self.tutor.caixa()]
        for c in self.carros:
            if any(c.rect.colliderect(b) for b in caixas):
                if not c.bateu:
                    c.bateu = True
                    self.m["col"] += 1
            elif c.v > 10 and not c.quase and not c.bateu and any(c.rect.inflate(36, 36).colliderect(b) for b in caixas):
                c.quase = True
                self.m["quase"] += 1

    # ---- navegação ----
    def _bip(self, pan, freq):
        if self.t_bip <= 0:
            self.bips.append((pan, freq))
            self.t_bip = 0.6

    def _mover(self, dt, wp):
        """Segue o waypoint do A* com evasão reativa baseada no LiDAR filtrado."""
        r = self.robo
        d = [l["distancia"] if l["tipo"] not in (None, "carro") else ALCANCE for l in r.leituras]
        t = N_RAIOS // 3
        esq, cen, dire = min(d[:t]), min(d[t:2 * t]), min(d[2 * t:])
        susp = any(l["tipo"] == "suspenso" and l["distancia"] < 115 for l in r.leituras[t:2 * t])
        vel = VEL
        if cen < 85:
            self.cor = VERMELHO
            self.status = "ALERTA CABEÇA: obstáculo alto! Desviando..." if susp else "OBSTÁCULO À FRENTE: contornando..."
        elif min(esq, dire) < 55:
            self.cor = LARANJA
            self.status = "Obstáculo à esquerda." if esq < dire else "Obstáculo à direita."
        else:
            self.cor, self.status = VERDE, f"Caminho livre. Guiando até {self.dest_nome}."
        if cen < 50:
            r.angulo += (-1 if esq > dire else 1) * 4.5 * dt
            vel = 0.35 * VEL
        elif esq < 32:
            r.angulo += 2.7 * dt
            vel = 0.85 * VEL
        elif dire < 32:
            r.angulo -= 2.7 * dt
            vel = 0.85 * VEL
        else:
            err = norma(math.atan2(wp[1] - r.y, wp[0] - r.x) - r.angulo)
            r.angulo += max(-5 * dt, min(5 * dt, err))
            if abs(err) > 0.6:
                vel = 0.25 * VEL
        if self.tensao > FOLGA_ARNES:                       # arnês esticado: desacelera
            vel *= max(0.15, 1 - (self.tensao - FOLGA_ARNES) / 20)
        r.x += math.cos(r.angulo) * vel * dt
        r.y += math.sin(r.angulo) * vel * dt
        r.passo_anim += vel * dt * 0.1
        if self.cor == VERMELHO or self.cor == LARANJA:
            lado = min(r.leituras, key=lambda l: l["distancia"] if l["tipo"] not in (None, "carro") else 1e9)
            self._bip(math.sin(lado["angulo"] - r.angulo) / math.sin(FOV / 2), 660)

    def _decidir(self, dt):
        r = self.robo
        if self.estado == "CHEGOU" or not self.path:
            if not self.path and self.estado != "CHEGOU":
                self.status, self.cor = "Sem rota até o destino.", LARANJA
                self.replanejar()
            return
        if self._perigo():                                    # segurança preditiva
            if self.estado != "FREIO_EMERGENCIA":
                self.estado_ant, self.estado = self.estado, "FREIO_EMERGENCIA"
                self.m["freios"] += 1
                self._bip(0.0, 990)
            self.t_livre = 0.0
        elif self.estado == "FREIO_EMERGENCIA":
            self.t_livre += dt
            if self.t_livre > 0.4:
                self.estado = self.estado_ant
        if self.estado == "FREIO_EMERGENCIA":
            self.cor, self.status = VERMELHO, "FREIO DE EMERGÊNCIA: veículo!"
            return

        while self.idx < len(self.path) - 1 and math.hypot(self.path[self.idx][0] - r.x, self.path[self.idx][1] - r.y) < 12:
            self.idx += 1
        wp = self.path[self.idx]
        if self.idx == len(self.path) - 1 and math.hypot(wp[0] - r.x, wp[1] - r.y) < 18:
            self.estado, self.cor = "CHEGOU", VERDE
            self.status = f"CHEGAMOS: {self.dest_nome}, com segurança!"
            self.viagens += 1
            return

        if self.estado == "NAVEGANDO" and RUA_Y - 10 <= wp[1] < RUA_FIM + 10:
            self.estado = "AGUARDANDO_SINAL"
        if self.estado == "AGUARDANDO_SINAL":
            if self._autorizado():
                self.estado, self.cruzando, self.de_cima = "ATRAVESSANDO", True, r.y < RUA_Y
            else:
                self.cor, self.status = LARANJA, "Aguardando sinal verde de pedestres."
                return
        if self.estado == "ATRAVESSANDO":
            if (self.de_cima and r.y > RUA_FIM + 12) or (not self.de_cima and r.y < RUA_Y - 12):
                self.estado, self.cruzando = "NAVEGANDO", False
            else:
                self.cor, self.status = VERDE, "Atravessando na faixa. Siga!"
                err = norma(math.atan2(wp[1] - r.y, wp[0] - r.x) - r.angulo)
                r.angulo += max(-5 * dt, min(5 * dt, err))
                v = VEL * (0.25 if abs(err) > 0.6 else 1.0)
                if self.tensao > FOLGA_ARNES:
                    v *= max(0.15, 1 - (self.tensao - FOLGA_ARNES) / 20)
                r.x += math.cos(r.angulo) * v * dt
                r.y += math.sin(r.angulo) * v * dt
                r.passo_anim += v * dt * 0.1
                return
        self._mover(dt, wp)

        self.t_preso += dt                                    # replaneja se preso em desvio local
        if self.t_preso >= TEMPO_PRESO:
            if math.hypot(r.x - self.ref_preso[0], r.y - self.ref_preso[1]) < 20 and self.estado == "NAVEGANDO":
                self.replanejar()
            self.ref_preso, self.t_preso = (r.x, r.y), 0.0

    def passo(self, dt, teclas=None):
        if self.pausa:
            return
        r = self.robo
        self.t_bip -= dt
        self.sinal.update(dt)
        fase = self.sinal.estado()[0]
        if self.fase_ant == "PEDESTRE" and fase != "PEDESTRE" and (
                self.cruzando or RUA_Y < self.tutor.y < RUA_FIM):
            self.m["sinal_fechou"] += 1
        self.fase_ant = fase
        self._carros(dt)
        alvos = [(o["rect"], o["tipo"]) for o in self.obst] + self.paredes + [(c.rect, "carro") for c in self.carros]
        r.ler_lidar(alvos, self.rng)
        r.px, r.py = r.x, r.y
        if self.autonomo:
            self._decidir(dt)
        elif teclas:
            if teclas[pygame.K_LEFT]:
                r.angulo -= 3 * dt
            if teclas[pygame.K_RIGHT]:
                r.angulo += 3 * dt
            if teclas[pygame.K_UP]:
                r.x += math.cos(r.angulo) * VEL * dt
                r.y += math.sin(r.angulo) * VEL * dt
                r.passo_anim += VEL * dt * 0.1
        self.aplicar_barreira()
        t = self.tutor                                        # tutor preso pelo arnês
        d = math.hypot(r.x - t.x, r.y - t.y)
        if d > GUIA:
            p = min(d - GUIA, TUTOR_VEL * dt)
            t.x += (r.x - t.x) / d * p
            t.y += (r.y - t.y) / d * p
        self.tensao = max(0.0, math.hypot(r.x - t.x, r.y - t.y) - GUIA)
        self._contagem_colisoes()
        em_alerta = self.cor == VERMELHO
        if em_alerta and not self.alerta_prev:
            self.m["alertas"] += 1
        self.alerta_prev = em_alerta
        if self.estado != "CHEGOU":
            self.m["t"] += dt
            self.m["dist"] += math.hypot(r.x - r.px, r.y - r.py) * PX_M


# ==================== BENCHMARK ====================
def benchmark(n, seed, p_infrator=0.3, t_max=120.0):
    rng = random.Random(seed)
    res = []
    for k in range(n):
        ini, dest = rng.sample([1, 2, 3, 4], 2)
        w = Mundo(rng, ini, dest, p_infrator)
        while w.estado != "CHEGOU" and w.m["t"] < t_max:
            w.passo(1 / FPS)
        ok = w.estado == "CHEGOU" and w.m["col"] == 0
        res.append((ok, w.m))
        print(f"  viagem {k + 1:2d}: {DESTINOS[ini][0]:>8} -> {DESTINOS[dest][0]:<8} "
              f"{'OK ' if ok else 'FALHA'} t={w.m['t']:5.1f}s col={w.m['col']} quase={w.m['quase']} freios={w.m['freios']}")
    chegou = [m for ok, m in res if ok]
    print(f"seed={seed} viagens={n} | sucesso={100 * len(chegou) / n:.0f}% | "
          f"tempo médio={statistics.mean(m['t'] for m in chegou) if chegou else float('nan'):.1f}s | "
          f"colisões={sum(m['col'] for _, m in res)} | quase-colisões={sum(m['quase'] for _, m in res)} | "
          f"freios={sum(m['freios'] for _, m in res)}")


# ==================== INTERFACE ====================
def fazer_bip(freq, pan, dur=0.12):
    """Bip sintético estéreo: pan -1 (só esquerda) a +1 (só direita)."""
    n, buf = int(44100 * dur), array("h")
    e, d = 1 - max(0, pan), 1 + min(0, pan)
    for k in range(n):
        s = 9000 * math.sin(2 * math.pi * freq * k / 44100) * (1 - k / n)
        buf.append(int(s * e))
        buf.append(int(s * d))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def quebrar(txt, n=24):
    linhas, atual = [], ""
    for p in txt.split():
        if len(atual) + len(p) + 1 > n:
            linhas.append(atual)
            atual = ""
        atual += p + " "
    return linhas + [atual]


def desenhar_luz(tela, x, y, fase):
    pygame.draw.rect(tela, PRETO, (x, y, 22, 44), border_radius=4)
    acesas = {"VERDE": 2, "AMARELO": 1}.get(fase, 0)
    for k, cor in enumerate([VERMELHO, (240, 200, 30), VERDE]):
        pygame.draw.circle(tela, cor if k == acesas else (60, 60, 60), (x + 11, y + 9 + k * 13), 5)
    pygame.draw.rect(tela, PRETO, (x + 26, y, 22, 44), border_radius=4)
    ped = fase == "PEDESTRE"
    pygame.draw.circle(tela, (60, 60, 60) if ped else VERMELHO, (x + 37, y + 12), 6)
    pygame.draw.circle(tela, VERDE if ped else (60, 60, 60), (x + 37, y + 32), 6)


def desenhar(tela, w, F, debug):
    tela.fill(CALCADA)
    pygame.draw.rect(tela, GRAMA, (0, 0, AREA, 28))
    pygame.draw.rect(tela, GRAMA, (0, ALTURA - 28, AREA, 28))
    pygame.draw.rect(tela, ASFALTO, (0, RUA_Y, AREA, RUA_H))
    for yy in (RUA_Y, RUA_FIM):
        pygame.draw.line(tela, MEIO_FIO, (0, yy), (AREA, yy), 4)
    for x in range(15, AREA - 20, 45):
        if not (FAIXA_X - 10 <= x <= FAIXA_X + FAIXA_W):
            pygame.draw.line(tela, BRANCO, (x, RUA_Y + RUA_H // 2), (x + 22, RUA_Y + RUA_H // 2), 3)
    for y in range(RUA_Y + 12, RUA_FIM - 12, 22):
        pygame.draw.rect(tela, BRANCO, (FAIXA_X, y, FAIXA_W, 12))
    for r in TATIL:
        pygame.draw.rect(tela, PISO_TATIL, r)
    if debug:
        bloq, _ = w.grade
        sup = pygame.Surface((AREA, ALTURA), pygame.SRCALPHA)
        for j in range(LINS):
            for i in range(COLS):
                if bloq[j][i]:
                    pygame.draw.rect(sup, (255, 0, 0, 60), (i * CELULA, j * CELULA, CELULA, CELULA))
        tela.blit(sup, (0, 0))
        if w.path and len(w.path) > 1:
            pygame.draw.lines(tela, (0, 120, 255), False, w.path, 2)
    fase, _ = w.sinal.estado()
    desenhar_luz(tela, FAIXA_X - 60, RUA_Y - 56, fase)
    desenhar_luz(tela, FAIXA_X + FAIXA_W + 12, RUA_FIM + 12, fase)
    for nome, (px, py) in DESTINOS.values():
        pygame.draw.circle(tela, (255, 120, 200), (px, py), 3)
    for o in w.obst:
        r = o["rect"]
        pygame.draw.rect(tela, (90, 95, 102), r.move(4, 4), border_radius=8)
        pygame.draw.rect(tela, o["cor"], r, border_radius=8)
        pygame.draw.rect(tela, BRANCO, r, 2, border_radius=8)
        lbl = F[2].render(o["nome"], True, BRANCO)
        tela.blit(lbl, (r.centerx - lbl.get_width() // 2, r.centery - 7))
    for c in w.carros:
        pygame.draw.rect(tela, c.cor, c.rect, border_radius=8)
        pygame.draw.rect(tela, BRANCO if c.infrator else PRETO, c.rect, 3 if c.infrator else 1, border_radius=8)
        vx = c.x + c.s * 10
        pygame.draw.rect(tela, (40, 60, 90), (vx - 5, c.y - 10, 10, 20), border_radius=3)
    w.robo.desenhar(tela, w.tutor)

    px = AREA
    pygame.draw.rect(tela, (36, 42, 58), (px, 0, LARGURA - px, ALTURA))
    x, y = px + 14, 14
    tela.blit(F[0].render("TELEMETRIA DOG-IA v2", True, (60, 170, 255)), (x, y))
    y += 34
    for txt, cor in [(f"Modo: {'AUTÔNOMO (IA)' if w.autonomo else 'MANUAL (setas)'}" + ("  [PAUSA]" if w.pausa else ""), BRANCO),
                     (f"Estado: {w.estado}", (110, 170, 255)),
                     (f"Destino: {w.dest_nome}", BRANCO),
                     (f"Pedestre: SIGA (PEDESTRE)" if fase == "PEDESTRE" else f"Pedestre: PARE ({fase})",
                      VERDE if fase == "PEDESTRE" else (255, 80, 80)),
                     (f"Áudio: {'LIGADO' if w.audio else 'DESLIGADO'} (M)", VERDE)]:
        tela.blit(F[1].render(txt, True, cor), (x, y))
        y += 22
    y += 6
    pygame.draw.rect(tela, w.cor, (x, y, 232, 78), border_radius=8)
    for k, ln in enumerate(quebrar(w.status)[:3]):
        tela.blit(F[1].render(ln, True, PRETO), (x + 10, y + 8 + k * 22))
    y += 92
    m = w.m
    tela.blit(F[3].render("MÉTRICAS DA VIAGEM", True, BRANCO), (x, y))
    y += 22
    for txt in [f"Tempo: {m['t']:.1f} s   Dist.: {m['dist']:.1f} m", f"Alertas: {m['alertas']}   Freios: {m['freios']}",
                f"Quase-colisões: {m['quase']}   Colisões: {m['col']}", f"Sinal fechou na travessia: {m['sinal_fechou']}",
                f"Viagens concluídas: {w.viagens}"]:
        tela.blit(F[2].render(txt, True, BRANCO), (x, y))
        y += 18
    y += 10
    tela.blit(F[3].render("CONTROLES", True, BRANCO), (x, y))
    y += 22
    for txt in ["DESTINOS: 1 Mercado  2 Farmácia", "          3 Padaria  4 Casa", "Clique esq: novo destino (calçada)",
                "Clique dir: criar obstáculo", "Clique meio: remover obstáculo", "ESPAÇO: autônomo / manual (setas)",
                "M: áudio  P: pausa  G: debug A*", "T: carro infrator  R: reiniciar", "F11 / ESC: tela cheia"]:
        tela.blit(F[2].render(txt, True, BRANCO), (x, y))
        y += 18


def main():
    pygame.init()
    tela = pygame.display.set_mode((LARGURA, ALTURA), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("DOG-IA v2 — Cão-guia robô (F11: tela cheia)")
    try:
        pygame.mixer.init(44100, -16, 2)
        pode_audio = True
    except pygame.error:
        pode_audio = False
    cache = {}
    F = [pygame.font.SysFont("arial", 20, bold=True), pygame.font.SysFont("arial", 15),
         pygame.font.SysFont("arial", 12, bold=True), pygame.font.SysFont("arial", 16, bold=True)]
    clock = pygame.time.Clock()
    rng = random.Random()
    w = Mundo(rng, inicio=4, destino=1)
    w.audio, debug = pode_audio, False

    def livre(mx, my):
        return (20 < mx < AREA - 20 and 35 < my < ALTURA - 35 and not (RUA_Y - 10 <= my < RUA_FIM + 10)
                and not any(o["rect"].inflate(20, 20).collidepoint(mx, my) for o in w.obst))

    rodando = True
    while rodando:
        dt = min(clock.tick(FPS) / 1000, 0.05)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                rodando = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.pos[0] < AREA:
                mx, my = ev.pos
                if ev.button == 1 and livre(mx, my):
                    w.nova_viagem("PONTO LIVRE", (mx, my))
                elif ev.button == 3:
                    w.obst.append({"rect": pygame.Rect(mx - 22, my - 22, 44, 44), "tipo": rng.choice(["solo", "suspenso"]),
                                   "nome": "OBSTÁCULO", "cor": (95, 100, 110)})
                    w.regrade()
                    w.replanejar()
                elif ev.button == 2:
                    w.obst = [o for o in w.obst if o["tipo"] == "edificio" or not o["rect"].collidepoint(mx, my)]
                    w.regrade()
                    w.replanejar()
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    w.nova_viagem(*DESTINOS[ev.key - pygame.K_0])
                elif ev.key == pygame.K_SPACE:
                    w.autonomo = not w.autonomo
                elif ev.key == pygame.K_p:
                    w.pausa = not w.pausa
                elif ev.key == pygame.K_g:
                    debug = not debug
                elif ev.key == pygame.K_m and pode_audio:
                    w.audio = not w.audio
                elif ev.key == pygame.K_t:
                    w.infrator()
                elif ev.key == pygame.K_r:
                    audio, v = w.audio, w.viagens
                    w = Mundo(rng, inicio=4, destino=1)
                    w.audio, w.viagens = audio, v
                elif ev.key == pygame.K_F11 or (ev.key == pygame.K_ESCAPE and pygame.display.is_fullscreen()):
                    pygame.display.toggle_fullscreen()
        w.passo(dt, pygame.key.get_pressed())
        for pan, freq in w.bips:
            if w.audio:
                k = (freq, round(pan, 1))
                cache.setdefault(k, fazer_bip(freq, pan)).play()
        w.bips.clear()
        desenhar(tela, w, F, debug)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", type=int, metavar="N", help="roda N viagens sem janela")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if a.benchmark:
        benchmark(a.benchmark, a.seed)
    else:
        main()
