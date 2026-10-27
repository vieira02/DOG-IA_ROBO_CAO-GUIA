from setuptools import find_packages, setup

package_name = 'dog_ia_core'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Samuel Solano Neres',
    maintainer_email='samuelsneres@gmail.com',
    description='Nucleo do DOG-IA: robo cao-guia urbano de inteligencia assistiva',
    license='MIT',
    entry_points={
        'console_scripts': [
            'valida_ambiente = dog_ia_core.valida_ambiente:main',
        ],
    },
)
