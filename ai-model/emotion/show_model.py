import tensorflow as tf

model = tf.keras.models.load_model(
    "ai-model/emotion/emotion_model.keras"
)

model.summary()