# Standard Library
import random
import pickle
from pathlib import Path
from typing import Union, Literal, Callable

# Third-Party Library
import numpy as np

# Torch Library
import torch
import torchvision.transforms
from torch.utils.data import Dataset


CIFAR_PATH: Path = (Path(__file__).resolve() /
                    "../../../data/cifar-100-python").resolve()


def check_cifar100(assertion: bool = True) -> bool:
    if assertion:
        assert CIFAR_PATH.exists(), f"Cifar100 is not downloaded! Please downloaded Cifar100 and extract to {
            CIFAR_PATH.relative_to(Path(__file__).parent.parent.parent.resolve())}"
    return CIFAR_PATH.exists()


def get_cifar100_cls_names() -> list[str]:
    meta = CIFAR_PATH / "meta"
    with meta.open(mode="rb") as f:
        data = pickle.load(f)

    return data['fine_label_names']


def get_data(split: Literal["train", "val", "test"]) -> tuple[np.ndarray | list[int]]:
    file = CIFAR_PATH / ("test" if split == "test" else "train")

    with file.open(mode="rb") as f:
        data = pickle.load(f, encoding="bytes")

    # TODO: how to split validation data?

    images = data[b"data"].reshape(-1, 3, 32, 32).transpose(0, 2, 3, 1)
    labels = data[b"fine_labels"]
    return images, labels


def get_task_data_getter(split: Literal["train", "val", "test"]) -> Callable[[list[str]], tuple[np.ndarray, list[int]]]:
    images, labels = get_data(split)

    labels = np.array(labels, dtype=np.int64)

    cls_id_mapper = {cls_name: cls_id for cls_id,
                     cls_name in enumerate(get_cifar100_cls_names())}

    def task_data_getter(cls_names: list[str]):
        task_images, task_labels = [], []

        for cls_name in cls_names:
            cls_mask = labels == cls_id_mapper[cls_name]
            task_images.append(images[cls_mask])
            task_labels.append(labels[cls_mask])

        return np.concatenate(task_images), np.concatenate(task_labels)

    return task_data_getter


def get_cifar100_tasks(cls_names: list[str], task_num: int = 10, fixed_tasks: bool = False) -> list[list[str]]:
    if fixed_tasks:
        return [['apple', 'aquarium_fish', 'baby', 'bear', 'beaver', 'bed', 'bee', 'beetle', 'bicycle', 'bottle'], ['bowl', 'boy', 'bridge', 'bus', 'butterfly', 'camel', 'can', 'castle', 'caterpillar', 'cattle'], ['chair', 'chimpanzee', 'clock', 'cloud', 'cockroach', 'couch', 'crab', 'crocodile', 'cup', 'dinosaur'], ['dolphin', 'elephant', 'flatfish', 'forest', 'fox', 'girl', 'hamster', 'house', 'kangaroo', 'keyboard'], ['lamp', 'lawn_mower', 'leopard', 'lion', 'lizard', 'lobster', 'man', 'maple_tree', 'motorcycle', 'mountain'], ['mouse', 'mushroom', 'oak_tree', 'orange', 'orchid', 'otter', 'palm_tree', 'pear', 'pickup_truck', 'pine_tree'], ['plain', 'plate', 'poppy', 'porcupine', 'possum', 'rabbit', 'raccoon', 'ray', 'road', 'rocket'], ['rose', 'sea', 'seal', 'shark', 'shrew', 'skunk', 'skyscraper', 'snail', 'snake', 'spider'], ['squirrel', 'streetcar', 'sunflower', 'sweet_pepper', 'table', 'tank', 'telephone', 'television', 'tiger', 'tractor'], ['train', 'trout', 'tulip', 'turtle', 'wardrobe', 'whale', 'willow_tree', 'wolf', 'woman', 'worm']]

    random.shuffle(cls_names)
    return [
        cls_names[i * 10: (i + 1) * 10]
        for i in range(len(cls_names) // task_num)
    ]


class Cifar100Dataset(Dataset):
    def __init__(self, images: np.ndarray, labels: np.ndarray, transforms) -> None:
        super().__init__()
        self.images = images
        self.labels = labels
        self.transforms = transforms

        self.to_tensor = torchvision.transforms.ToTensor()

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index) -> tuple[torch.FloatTensor, torch.FloatTensor]:
        image = self.to_tensor(self.images[index])
        return self.transforms(image), self.labels[index]


if __name__ == "__main__":
    cls_names = get_cifar100_cls_names()
    tasks = get_cifar100_tasks(cls_names)
    task_data_getter = get_task_data_getter("train")

    task_images, task_labels = task_data_getter(tasks[0])

    print(1)