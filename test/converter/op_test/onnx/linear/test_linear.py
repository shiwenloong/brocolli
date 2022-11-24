import torch
import pytest
import warnings

from brocolli.testing.common_utils import OnnxBaseTester as Tester


def test_Linear_basic(
    shape=[1, 3],
):
    model = torch.nn.Linear(3, 5, bias=True)
    Tester("Linear_basic", model, shape)


def test_Linear_nobias(
    shape=[1, 3],
):
    model = torch.nn.Linear(3, 5, bias=False)
    Tester("Linear_nobias", model, shape)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    pytest.main(["-p", "no:warnings", "-v", "test/op_test/onnx/linear/test_linear.py"])
