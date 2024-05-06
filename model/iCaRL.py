# Standard Library
import copy
from typing import Optional
from contextlib import contextmanager

# Third-Party Library

# Torch Library
import torch
import torch.nn as nn
import torchvision.models as models
from torchvision.models.resnet import ResNet

# My Library
from utils.annotation import Task


class iCaRL(nn.Module):

    def __init__(self, feature_dim: int = 2048) -> None:
        super().__init__()
        self.feature_extractor: ResNet = models.resnet18(
            weights=models.ResNet18_Weights.DEFAULT)

        # Note: when input batched image is [1, C, H, W], resnet will be wrong for Resnet._forward_impl.layer4(x)
        # Note: this is because the maxpool layer. So, remove the maxpool
        # Note: check module/resnet.py for my implementation
        self.feature_extractor.maxpool = nn.Identity()

        # map the features from feature space into prototype space
        self.feature_extractor.fc = nn.Linear(
            self.feature_extractor.fc.in_features, feature_dim)
        self.feature_dim = self.feature_extractor.fc.out_features

        self.previous_feature_extractor: ResNet = None

        # Note: iCaRL uses weight vectors for representation learning, not classification
        # Ref: Page 3, Architecture, Paragraph 2, Line 11: "Note that even though one can interpret these outputs as probabilities, iCaRL uses the network only for representation learning, not for the actual classification step."
        self.weight_vectors: list[nn.Linear] = []
        self.current_weight_vectors: nn.Linear = None

        # Note: iCaRL uses Nearest-Mean-of-Exemplars to classify a given example
        self.exemplar_means: dict[str, torch.FloatTensor] = {}

        self.current_task: Task = None
        self.learned_classes = []

    @contextmanager
    def set_new_task(self, task: Task):
        num_cls = len(task)
        self.current_task = task

        # create new weight vectors
        self.current_weight_vectors = nn.Linear(
            in_features=self.feature_dim, out_features=num_cls + len(self.learned_classes), bias=False).to(device=self.feature_extractor.conv1.weight.device)

        if len(self.weight_vectors) != 0:
            previous_weight_vector = self.weight_vectors[-1]

            self.current_weight_vectors.weight.data[:len(
                self.learned_classes), :] = previous_weight_vector.weight.data[:, :]

        self.weight_vectors.append(self.current_weight_vectors)

        # copy the last feature extractor
        self.previous_feature_extractor = copy.deepcopy(self.feature_extractor)

        try:
            yield self
        finally:
            self.learned_classes.extend(task)

    @contextmanager
    def use_previous_model(self, feature_extractor: Optional[ResNet] = None, weight_vectors: Optional[nn.Linear] = None):
        current_feature_extractor = self.feature_extractor
        current_weight_vectors = self.current_weight_vectors

        try:
            self.feature_extractor = feature_extractor if feature_extractor is not None else self.previous_feature_extractor
            self.current_weight_vectors = weight_vectors if weight_vectors is not None else self.weight_vectors[-2]
            yield self
        finally:
            self.feature_extractor = current_feature_extractor
            self.current_weight_vectors = current_weight_vectors

    def forward(self, image: torch.FloatTensor) -> torch.FloatTensor:
        """
        Args:
            image (torch.FloatTensor): input image, shape [B, C, H, W]
        Returns:
            torch.FloatTensor: output logits, shape [B, N] (N for number of classes learned so far)
        """

        # sourcery skip: inline-immediately-returned-variable
        features: torch.FloatTensor
        logits: torch.FloatTensor

        features = self.feature_extractor(image)

        logits = self.current_weight_vectors(features)

        return logits

    @torch.no_grad()
    def get_preds(self, image: torch.FloatTensor) -> torch.FloatTensor:
        """
        Args:
            image (torch.FloatTensor): input image, shape [B, C, H, W]
        Returns:
            torch.FloatTensor: output predictions, shape [B]
        """

        features: torch.FloatTensor
        # [B, 512]
        features = self.feature_extractor(image)

        # Note: iCaRL L2-normalizes the features
        # ref: Page 2, Architecture, Paragraph 1, Line 5: "All feature vectors are L2-normalized..."
        features = features / features.norm(p=2, dim=1, keepdim=True)

        # [B, 1, 512]
        features = features.unsqueeze(dim=1)

        # [1, N, 512]
        cls_means: torch.FloatTensor = torch.cat(
            list(self.exemplar_means.values()), dim=0).unsqueeze(dim=0)

        # [B, N, 512]
        pred = features - cls_means
        # [B, N]
        pred = pred.norm(p=2, dim=2, keepdim=False)
        return pred.argmin(dim=1)


if __name__ == "__main__":
    from utils.datasets import CLDatasetGetter
    from torch.utils.data import DataLoader

    model = iCaRL()
    model = model.to("cuda:0")

    train_image = torch.randn(64, 3, 32, 32).to("cuda:0")
    test_image = torch.randn(16, 3, 32, 32).to("cuda:0")

    with model.set_new_task(t := ["1", "2", "3"]):
        logits = model(train_image)

        # calculate mean of class
        for i, t_name in enumerate(t):
            model.exemplar_means[t_name] = (
                torch.ones(1, 512) * i).to("cuda:0")

        pred = model.get_preds(test_image)
