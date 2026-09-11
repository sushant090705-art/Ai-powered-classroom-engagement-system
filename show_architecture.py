import tensorflow as tf
from tensorflow.keras.utils import plot_model

model = tf.keras.models.load_model(
    "ai-model/emotion/emotion_model.keras"
)

plot_model(
    model,
    to_file="emotion_model_architecture.png",
    show_shapes=True,
    show_layer_names=True
)

print("Architecture image created!")