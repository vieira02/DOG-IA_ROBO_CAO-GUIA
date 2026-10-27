#!/usr/bin/env python3
# Define o interpretador Python 3 para a execução do script.

import rclpy
# Importa a biblioteca oficial do ROS 2 para Python (rclpy).

from rclpy.node import Node
# Importa a classe base 'Node' necessária para criar nós do ROS 2.

import cv2  # noqa: F401
# Importa a biblioteca OpenCV; falha aqui indica que o OpenCV não está instalado.

from cv_bridge import CvBridge
# Importa o conversor de mensagens de imagem do ROS para OpenCV.

from std_msgs.msg import String
# Importa o tipo de mensagem textual padrão (String).


class ValidaAmbienteNode(Node):
    """
    Nó de validação do ambiente.
    Herda da classe 'Node' do ROS 2.
    """

    def __init__(self):
        super().__init__('valida_ambiente_node')
        # Inicializa o nó com o nome registrado 'valida_ambiente_node'.

        self.bridge = CvBridge()
        # Instancia o objeto de ponte entre ROS e OpenCV.

        self.publisher_ = self.create_publisher(String, 'dog_ia/status', 10)
        # Cria o publicador no tópico 'dog_ia/status' com fila de tamanho 10.

        self.timer = self.create_timer(2.0, self.publica_status)
        # Configura um temporizador que chama 'publica_status' a cada 2.0 segundos.

        self.get_logger().info("✅ Nó de Validação do DOG-IA iniciado com sucesso!")
        # Exibe no log do terminal a confirmação de inicialização.

    def publica_status(self):
        """Callback executado periodicamente pelo temporizador."""
        msg = String()
        # Instancia uma nova mensagem do tipo String.

        msg.data = "DOG-IA Operacional: ROS 2 + OpenCV Prontos!"
        # Atribui o conteúdo textual à mensagem.

        self.publisher_.publish(msg)
        # Envia a mensagem para o tópico registrado.

        self.get_logger().info(f'Mensagem Publicada: "{msg.data}"')
        # Registra no console a confirmação do envio.


def main(args=None):
    """Função de inicialização e execução do nó."""
    rclpy.init(args=args)
    # Inicializa as comunicações do ROS 2.

    node = ValidaAmbienteNode()
    # Instancia a classe do nó.

    try:
        rclpy.spin(node)
        # Mantém o nó rodando e aguardando eventos até interrupção (Ctrl+C).
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        # Finaliza e destrói o nó.

        rclpy.shutdown()
        # Encerra o sistema de comunicação do ROS 2.


if __name__ == '__main__':
    main()
    # Ponto de entrada do script.
