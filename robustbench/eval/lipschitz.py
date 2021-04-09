from typing import Optional

import torch
from torch import nn
from torch.utils.data import DataLoader


def box(x_prime: torch.Tensor, x: torch.Tensor, eps: float) -> torch.Tensor:
    min_x = torch.max(torch.zeros(x.shape), x - eps)
    max_x = torch.min(torch.ones(x.shape), x + eps)

    return torch.max(min_x, torch.min(x_prime, max_x))


def compute_lipschitz_batch(model: nn.Module,
                            x: torch.Tensor,
                            eps: float,
                            step_size: float,
                            n_steps: int = 50) -> float:
    """Computes local (i.e. eps-ball) Lipschitzness of the given `model` on
    a batch of data.
    """

    # Function to differentiate
    def f(x_prime_: torch.Tensor) -> torch.Tensor:
        numerator = torch.norm(model(x) - model(x_prime_), p=1, dim=1)
        denominator = torch.norm(x - x_prime_, p=float("inf"), dim=1)
        return (numerator / denominator).mean()

    # Initialize to a slightly different random value
    x_prime = box(x + step_size * torch.randn_like(x), x, eps)
    x_prime.requires_grad = True

    for i in range(n_steps):
        y = f(x_prime)
        y.backward()
        grads_x_prime = x_prime.grad
        x_prime = box(x_prime.detach() + step_size * grads_x_prime, x,
                      eps).requires_grad_(True)

    return torch.mean(f(x_prime)).item()


def compute_lipschitz(model: nn.Module,
                      dl: DataLoader,
                      eps: float,
                      step_size: float,
                      n_steps: int = 50,
                      device: Optional[torch.device] = None):
    """Computes local (i.e. eps-ball) Lipschitzness of the given `model`.

    We use the method proposed by Yang et al. [1]_.

    .. [1] Yao-Yuan Yang, Cyrus Rashtchian, Hongyang Zhang, Russ R. Salakhutdinov,
        Kamalika Chaudhuri, A Closer Look at Accuracy vs. Robustness, NeurIPS 2020.

    :param model: The model whose Lipschitzness has to be computed.
    :param dl: The dataloader of data to compute Lipschitzness on.
    :param eps: The ball boundary (around each sample)
    :param step_size: The step size of the each step.
    :param n_steps: The number of steps to run.
    :param device: The device to run computations.

    :return: The local Lipschitz constant.
    """
    if device is None:
        device = torch.device("cpu")

    model_dev = model.to(device)

    lips = 0.
    for x, _ in dl:
        x_dev = x.to(device)
        batch_lips = compute_lipschitz_batch(model_dev, x_dev, eps, step_size,
                                             n_steps)
        lips += batch_lips

    return lips / len(dl)
