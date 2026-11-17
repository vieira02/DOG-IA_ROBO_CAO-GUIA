# DOG-IA — Respostas AC-4 (questões preparatórias)

Código: `dog_ia_v2.py` (Marcos 1–4). Benchmark: `python dog_ia_v2.py --benchmark 20 --seed 1`.

## 1. Arquitetura híbrida (global vs. local)

**1.1 — Qual limitação crítica da navegação puramente reativa é resolvida e por que o planejador global sozinho não basta?**

A navegação reativa só enxerga o que o LiDAR alcança (165 px). Ela não tem memória nem objetivo de longo prazo, então fica presa em **mínimos locais** (obstáculo em "U": desviar de um lado leva ao outro e o robô oscila). Ela também não sabe escolher uma rota boa: não prefere o piso tátil, não sabe que precisa ir até a faixa de pedestres e não lida com vários destinos.

O A* resolve isso porque enxerga o mapa inteiro, mas a grade é um retrato estático. Ela não contém carros em movimento, obstáculos criados depois do planejamento, o ruído do sensor nem o estado do semáforo. O planejador também é lento demais para reagir a cada quadro. Por isso o A* define a rota (e é refeito se o robô ficar preso por mais de 3,5 s ou se o mapa mudar), e a camada reativa com LiDAR desvia do que o mapa não conhecia.

## 2. Máquina de estados

**2.1 — Estados de uma viagem completa (1 = Mercado, saindo de Casa) e as transições**

Trace real da simulação (semáforo em VERDE ao chegar na calçada):

| # | Estado | Transição para o próximo |
|---|--------|--------------------------|
| 1 | `NAVEGANDO` | o próximo waypoint do A* está sobre a faixa (meio-fio) |
| 2 | `AGUARDANDO_SINAL` | fase = `PEDESTRE` **e** `tempo_restante > 2,44 s` **e** nenhum carro em movimento chegando na faixa em 2,5 s |
| 3 | `ATRAVESSANDO` | o robô passa do meio-fio oposto (`y > 432`) |
| 4 | `NAVEGANDO` | distância ao último waypoint < 18 px |
| 5 | `CHEGOU` | fim da viagem (`viagens += 1`) |

Se o semáforo já estiver aberto para pedestres ao chegar, o estado 2 é pulado. `FREIO_EMERGENCIA` pode entrar entre qualquer um desses (ver 2.2).

**2.2 — Diferença entre `AGUARDANDO_SINAL` e `FREIO_EMERGENCIA`**

- `AGUARDANDO_SINAL` é uma **parada planejada e previsível**. O robô está no meio-fio, o sinal está fechado ou o tempo restante é insuficiente, e ele espera sem risco imediato.
- `FREIO_EMERGENCIA` é uma **reação a perigo iminente**. A zona varrida de um veículo (posição + 1,0 s de movimento) intercepta o robô ou o tutor, e isso pode acontecer em qualquer estado, sobretudo no meio da travessia. O robô para na hora, soma 1 em "Freios" e guarda o estado anterior. Só volta a ele depois de 0,4 s sem perigo.

## 3. Percepção e ruído do sensor

**3.1 — Por que a mediana é melhor que a média para "leitura = alcance máximo"?**

Uma falha (dropout) é um *outlier* de valor extremo. Com leituras 60, 165, 60 px, a média dá 95 px: o obstáculo parece mais longe do que está, e o erro cresce com o tamanho do outlier. A mediana dá 60 px, porque ignora o valor extremo. Ela rejeita até 1 outlier em 3 sem nenhum erro. Com 2% de dropout por raio, dois erros seguidos no mesmo raio têm cerca de 3·0,02² ≈ 0,12% de chance.

**3.2 — Atraso do filtro (60 varreduras/s)**

Um obstáculo novo só vira mediana quando 2 das 3 últimas varreduras o veem. Isso custa **1 varredura extra** de atraso: 1/60 ≈ **0,017 s (≈17 ms)**. Nessa janela o robô anda 156 × 0,017 ≈ 2,6 px.

**3.3 — E se a janela tivesse 15 varreduras?**

A maioria passa a ser 8 das 15, então o atraso sobe para 7 varreduras extras: 7/60 ≈ **0,12 s (≈117 ms)**, ou cerca de 18 px de deslocamento às cegas. O filtro rejeitaria mais ruído e falhas em sequência, mas o robô reagiria tarde a obstáculos e carros, o que é perigoso na travessia. Haveria também mais memória e mais custo de ordenação por raio.

## 4. Segurança temporal na travessia

**4.1 — Limite com os valores do código**

```
(170 + 24 + 42) / 156 × 1,35 + 0,4
= 236 / 156 × 1,35 + 0,4
= 1,513 × 1,35 + 0,4
≈ 2,44 s
```

A travessia só começa se restarem mais de 2,44 s da fase `PEDESTRE`. Isso inclui 35% de margem sobre o tempo teórico, mais 0,4 s de reação.

**4.2 — Por que as fases "todos vermelhos" de 1,5 s?**

É o *clearance interval*. Elas eliminam o **conflito entre quem ainda está dentro do cruzamento e quem recebe sinal para entrar**:

- `TODOS_VERM_1`: o carro que entrou no amarelo (ou não conseguiu frear) termina de sair da faixa antes de os pedestres começarem. Um carro a 130 px/s leva ~1,2 s para cruzar 95 px de faixa + 54 px de comprimento.
- `TODOS_VERM_2`: o pedestre mais lento (o tutor, ~42 px atrás do robô) termina de sair da rua antes de os carros partirem.

Sem elas, haveria atropelamento por carro atrasado ou por arrancada simultânea.

## 5. Avaliação experimental

Condições: 20 viagens por execução, origem e destino sorteados entre Mercado, Farmácia, Padaria e Casa, fase inicial do semáforo aleatória, 30% dos carros infratores, tempo máximo de 120 s por viagem. Sucesso = chegou sem colisão.

**5.1 — Resultados**

| | `--seed 1` | `--seed 7` |
|---|---|---|
| Taxa de sucesso | 100% (20/20) | 100% (20/20) |
| Tempo médio | 11,1 s | 10,0 s |
| Colisões | 0 | 0 |
| Quase-colisões | 0 | 0 |
| Freios de emergência | 1 | 2 |

**5.2 — Por que a seed fixa dá reprodutibilidade, e por que as seeds diferem?**

A seed inicializa o gerador pseudoaleatório, que é determinístico. Ela alimenta o ruído gaussiano, os dropouts, os intervalos de chegada dos carros, a escolha dos infratores, a fase inicial do semáforo e os pares origem/destino. Com o mesmo código e a mesma seed a sequência é idêntica (rodar `--seed 1` duas vezes deu exatamente o mesmo resultado).

Seeds diferentes geram sequências diferentes. O tempo de espera no semáforo depende da fase inicial, o trajeto depende do par origem/destino, e os carros infratores chegam em momentos distintos. Assim o tempo médio e o número de freios mudam (11,1 s vs 10,0 s; 1 vs 2 freios), embora ambas as seeds tenham tido 100% de sucesso. Com 20 viagens só, essas diferenças são ruído amostral.

**5.3 — Melhoria proposta**

Aumentar a janela de predição da zona varrida de 1,0 s para 1,5 s e a margem de segurança de 1,35 para 1,6 no critério de travessia.

- **Esperado melhorar:** quase-colisões e colisões, porque o robô freia mais cedo e só atravessa com folga maior.
- **Esperado piorar:** tempo médio de viagem e número de freios, porque o robô espera mais em alguns ciclos e dispara o freio em situações que não seriam perigosas.

Essa previsão não foi medida; seria testada rodando o benchmark com as duas seeds antes e depois da mudança.
