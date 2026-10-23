"""Loads the Fashion-MNIST idx files in this folder as NumPy arrays.

    from load_fashion import load_fashion, CLASS_NAMES
    x_train, y_train, x_test, y_test = load_fashion()   # (60000, 28, 28) uint8, (60000,), (10000, 28, 28), (10000,)
"""
import gzip
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CLASS_NAMES = ["T-shirt/top", "Trouser", "Pullover", "Dress", "Coat", "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"]


def _images(name):
    with gzip.open(HERE / name, "rb") as f:
        return np.frombuffer(f.read(), dtype=np.uint8, offset=16).reshape(-1, 28, 28)


def _labels(name):
    with gzip.open(HERE / name, "rb") as f:
        return np.frombuffer(f.read(), dtype=np.uint8, offset=8)


def load_fashion():
    return (
        _images("train-images-idx3-ubyte.gz"), _labels("train-labels-idx1-ubyte.gz"),
        _images("t10k-images-idx3-ubyte.gz"), _labels("t10k-labels-idx1-ubyte.gz"),
    )


if __name__ == "__main__":
    xt, yt, xs, ys = load_fashion()
    print(xt.shape, yt.shape, xs.shape, ys.shape)
