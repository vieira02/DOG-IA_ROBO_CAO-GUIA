Escopo do Projeto DOG-IA - Robô Cão-Guia Urbano de Inteligência Assistiva

1. Visão Geral

O projeto DOG-IA - Robô Cão-Guia Urbano de Inteligência Assistiva tem como objetivo desenvolver um protótipo de robô-guia autônomo em ambiente urbano simulado, utilizando tecnologias de robótica, inteligência assistiva, navegação autônoma e visão computacional.

O sistema será desenvolvido para atuar à frente de uma pessoa com deficiência visual, auxiliando sua mobilidade por meio da identificação do ambiente, navegação segura, detecção de obstáculos, reconhecimento de sinalização urbana e emissão de orientações por voz ou som.

O projeto será desenvolvido de forma incremental, dividido nas fases AC-3 e AC-4, conforme as etapas estabelecidas no Guia Oficial do Projeto.

2. Objetivo Geral

Desenvolver e demonstrar um protótipo de robô cão-guia capaz de navegar de maneira autônoma em um ambiente urbano simulado, identificando obstáculos e elementos de sinalização e fornecendo orientações ao usuário em tempo real.

3. Objetivos Específicos

O sistema deverá:

* Navegar autonomamente pelo ambiente urbano simulado.
* Mapear o ambiente utilizando sensores e técnicas de SLAM.
* Detectar obstáculos presentes no percurso.
* Detectar obstáculos suspensos ou aéreos.
* Identificar possíveis buracos ou regiões que representem risco à navegação.
* Reconhecer sinais de trânsito por meio de visão computacional.
* Identificar o estado do semáforo, especialmente as condições verde e vermelho.
* Identificar faixas de pedestres no ambiente simulado.
* Impedir o robô de atravessar a rua quando o sinal estiver vermelho.
* Emitir orientações sonoras ou de voz ao usuário.
* Demonstrar o funcionamento completo do sistema de forma autônoma no simulador.

4. Ambiente e Tecnologias

O desenvolvimento será realizado em ambiente simulado, utilizando as seguintes tecnologias e ferramentas previstas no projeto:

* Ubuntu 22.04 ou WSL2 no Windows;
* ROS 2 Humble/Jazzy;
* Gazebo;
* RViz2;
* Python;
* OpenCV;
* cv_bridge;
* SLAM Toolbox;
* Nav2;
* URDF/Xacro;
* Git/GitHub.

5. Componentes do Robô

O modelo simulado do robô deverá possuir:

* Duas rodas motrizes;
* Uma roda boba;
* Câmera RGB-D para percepção tridimensional;
* LiDAR 2D instalado no chassi;
* Sistema de controle diferencial;
* Publicação de odometria;
* Estrutura de transformações TF2;
* Integração com os componentes do ROS 2.

6. Escopo da Fase AC-3

A primeira fase será dedicada à infraestrutura, modelagem e navegação.

6.1 Preparação do Ambiente

Será realizada a configuração e validação do ambiente de desenvolvimento, incluindo ROS 2, Gazebo e RViz2, além da criação do workspace do ROS 2 e do repositório Git do grupo.

6.2 Modelagem do Robô

Será desenvolvido o modelo físico simulado do DOG-IA utilizando URDF/Xacro.

O modelo deverá contemplar as rodas, sensores e elementos necessários para sua movimentação e percepção do ambiente.

6.3 Sensores

Será realizada a configuração da câmera RGB-D e do LiDAR 2D.

A câmera deverá ser posicionada de forma a auxiliar na identificação de obstáculos suspensos, enquanto o LiDAR será utilizado para auxiliar na percepção do ambiente e navegação.

6.4 Navegação e Mapeamento

O robô deverá realizar o mapeamento do ambiente urbano utilizando o SLAM Toolbox.

Também será configurado o Nav2, incluindo:

* Costmap local;
* Costmap global;
* Planejadores de trajetória;
* Raio de inflação para manter distância segura dos obstáculos.

Ao final da fase, o robô deverá ser capaz de navegar autonomamente até um ponto determinado no ambiente simulado.

7. Escopo da Fase AC-4

A segunda fase será dedicada à inteligência, percepção e interação humano-robô.

7.1 Visão Computacional

Será desenvolvido um nó em Python integrado ao ROS 2 e ao OpenCV por meio do cv_bridge.

O sistema deverá processar as imagens provenientes da câmera para identificar:

* Cor do semáforo;
* Sinal verde;
* Sinal vermelho;
* Faixa de pedestres.

7.2 Controle de Travessia

O sistema deverá possuir uma lógica de segurança capaz de impedir que o robô atravesse a rua quando o semáforo estiver vermelho.

Ao detectar essa condição, o robô deverá interromper sua trajetória.

7.3 Interação Humano-Robô

Será desenvolvido um sistema de áudio utilizando bibliotecas de Text-to-Speech em Python.

O sistema deverá fornecer orientações ao usuário, podendo emitir mensagens relacionadas a:

* Sinal vermelho;
* Aguarde na calçada;
* Orientação de percurso;
* Distância até determinado ponto;
* Detecção de obstáculo suspenso.

7.4 Testes e Robustez

Serão realizados testes de estresse no sistema, buscando identificar problemas e melhorar a robustez do código e do comportamento do robô durante a simulação.

8. Arquitetura do Sistema

A arquitetura deverá representar a comunicação entre os componentes do sistema ROS 2, incluindo:

* Nós;
* Tópicos;
* Serviços;
* Ações;
* Árvore de transformações TF2;
* Sensores;
* Sistema de navegação;
* Sistema de visão computacional;
* Sistema de áudio.

Os diagramas completos da arquitetura deverão ser apresentados como parte dos artefatos técnicos do projeto.

9. Entregáveis

O projeto deverá resultar nos seguintes artefatos:

9.1 Código-Fonte

Repositório contendo os pacotes ROS 2 desenvolvidos em Python, modelos URDF/Xacro, arquivos .launch.py e configurações do Nav2.

9.2 Arquitetura do Sistema

Diagramas completos demonstrando a estrutura e comunicação dos componentes do ROS 2, incluindo nós, tópicos, serviços, ações e TF2.

9.3 Relatório Técnico

Documento contendo a descrição da solução, metodologia utilizada, experimentos realizados e análise dos resultados obtidos.

9.4 Vídeo de Demonstração

Vídeo de aproximadamente 2 a 3 minutos demonstrando, por meio de gravação de tela, o robô cumprindo as missões propostas de maneira autônoma no simulador.

9.5 Apresentação

Apresentação do projeto para a turma, demonstrando o funcionamento do protótipo no Gazebo/RViz2 e o cumprimento da missão de guiamento.

10. Critérios de Validação

O projeto será considerado funcional quando o robô for capaz de:

1. Carregar corretamente no Gazebo.
2. Responder aos comandos de movimentação durante a etapa de desenvolvimento.
3. Publicar corretamente as transformações TF.
4. Mapear o ambiente urbano.
5. Navegar autonomamente até um ponto determinado.
6. Detectar elementos relevantes por meio da visão computacional.
7. Interromper a trajetória diante de um sinal vermelho.
8. Detectar obstáculos relevantes ao percurso.
9. Emitir orientações de voz ao usuário.
10. Completar a missão de guiamento de forma autônoma no ambiente simulado.

11. Limitações do Projeto

O DOG-IA será desenvolvido como um protótipo em ambiente simulado. Portanto, o projeto não tem como objetivo, dentro deste escopo, construir ou operar um robô físico em ambientes urbanos reais.

Os testes, validações e demonstrações serão realizados no ambiente de simulação definido para o projeto.

12. Resultado Esperado

Ao final das fases AC-3 e AC-4, espera-se obter um protótipo funcional de robô cão-guia capaz de realizar autonomamente uma missão de guiamento em ambiente urbano simulado, utilizando sensores, mapeamento, navegação, visão computacional e comunicação por áudio.

O resultado final deverá demonstrar a integração dos diferentes componentes do sistema e sua aplicação na mobilidade assistiva para pessoas com deficiência visual.
