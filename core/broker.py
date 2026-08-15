# /home/ernesto/MotorDICOM/core/broker.py
from huey import SqliteHuey

# Utilizamos SqliteHuey para persistir la cola localmente. 
# Esto garantiza compatibilidad nativa tanto en entornos Linux como Windows sin necesidad de contenedores extra.
huey = SqliteHuey(filename='motor_queue.db')