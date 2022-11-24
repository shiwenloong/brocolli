import numpy as np

np.random.seed(0)

from loguru import logger

from brocolli.converter.onnx_layers import *
from brocolli.converter.pytorch_graph import PytorchGraph
from brocolli.converter.utils import (
    fuse_all_conv_bn,
    get_function_name,
    map_replace,
    get_torch_size,
    gen_torch_tensor,
    map_reduce,
    gen_numpy_data,
    optimize_model,
)

import torch

torch.manual_seed(0)
import torch.nn as nn
from torch.fx.graph_module import GraphModule

from onnx import save, helper, checker


class PytorchOnnxParser:
    def __init__(
        self, model, input_shape, fuse=False, concrete_args=None, dynamic_batch=False
    ):
        super(PytorchOnnxParser, self).__init__()
        self.fuse = fuse
        self.model = model.eval()
        self.input_shape = map_replace(input_shape, get_torch_size)
        if isinstance(self.input_shape, torch.Size):
            self.input_shape = [self.input_shape]
        self.concrete_args = concrete_args
        self.dynamic_batch = dynamic_batch

        if isinstance(self.model, GraphModule):
            pass
        elif isinstance(self.model, nn.Module):
            if self.fuse:
                fuse_all_conv_bn(self.model)
        else:
            raise Exception("model must be a torch.nn.Module or a torch.fx.GraphModule")

        self.pytorch_graph = PytorchGraph(
            self.model, self.input_shape, self.concrete_args, self.dynamic_batch
        )
        self.state_dict = self.pytorch_graph.graph_module.state_dict()
        self.modules = dict(self.pytorch_graph.graph_module.named_modules())
        self.in_tensor_value_info = []
        self.nodes = []
        self.out_tensor_value_info = []
        self.init_tensor = []
        self.value_info = []

    def convert(self):
        self.gen_ir()

    def gen_ir(self):
        for node in self.pytorch_graph.nodes:
            if node.op == "placeholder":
                input_layer = InputLayer(node)
                self.node_post_process(input_layer)
            elif node.op == "call_module":
                module = self.modules[node.target]
                if isinstance(module, (nn.Conv2d, nn.Conv1d)):
                    conv_layer = ConvLayer(node, module)
                    self.node_post_process(conv_layer)
                elif isinstance(module, nn.BatchNorm2d):
                    batchnorm_layer = BatchNormLayer(node, module)
                    self.node_post_process(batchnorm_layer)
                elif isinstance(module, nn.ReLU):
                    relu_layer = ReluLayer(node, module)
                    self.node_post_process(relu_layer)
                elif isinstance(module, (nn.MaxPool1d, nn.MaxPool2d)):
                    pooling_layer = PoolingLayer(node, module)
                    self.node_post_process(pooling_layer)
                elif isinstance(module, (nn.AdaptiveAvgPool1d, nn.AdaptiveAvgPool2d)):
                    pooling_layer = PoolingLayer(node, module)
                    self.node_post_process(pooling_layer)
                elif isinstance(module, nn.Linear):
                    linear_layer = LinearLayer(node, module)
                    self.node_post_process(linear_layer)
                elif isinstance(module, nn.Dropout):
                    dropout_layer = DropoutLayer(node, module)
                    self.node_post_process(dropout_layer)
                elif isinstance(module, nn.ReLU6):
                    relu6_layer = Relu6Layer(node, module)
                    self.node_post_process(relu6_layer)
                elif isinstance(module, nn.Hardswish):
                    hardsiwsh_layer = HardswishLayer(node, module)
                    self.node_post_process(hardsiwsh_layer)
                elif isinstance(module, nn.Hardsigmoid):
                    hardsigmoid_layer = HardsigmoidLayer(node, module)
                    self.node_post_process(hardsigmoid_layer)
                elif isinstance(module, nn.Identity):
                    identity_layer = IdentityLayer(node, module)
                    self.node_post_process(identity_layer)
                elif isinstance(module, (nn.AvgPool1d, nn.AvgPool2d)):
                    avgpool_layer = AvgPoolLayer(node, module)
                    self.node_post_process(avgpool_layer)
                elif isinstance(module, nn.Upsample):
                    upsample_layer = UpsampleLayer(node, module)
                    self.node_post_process(upsample_layer)
                elif isinstance(module, nn.PReLU):
                    prelu_layer = PReluLayer(node, module)
                    self.node_post_process(prelu_layer)
                elif isinstance(module, (nn.ConvTranspose1d, nn.ConvTranspose2d)):
                    conv_transpose_layer = ConvTransposeLayer(node, module)
                    self.node_post_process(conv_transpose_layer)
                elif isinstance(module, nn.LSTM):
                    lstm_layer = LSTMLayer(node, module)
                    self.node_post_process(lstm_layer)
                elif isinstance(module, nn.RNN):
                    rnn_layer = RNNLayer(node, module)
                    self.node_post_process(rnn_layer)
                elif isinstance(module, nn.GRU):
                    gru_layer = GRULayer(node, module)
                    self.node_post_process(gru_layer)
                elif isinstance(module, nn.Flatten):
                    flatten_layer = FlattenLayer(node, module)
                    self.node_post_process(flatten_layer)
                elif isinstance(module, nn.LeakyReLU):
                    leakyrelu_layer = LeakyReluLayer(node, module)
                    self.node_post_process(leakyrelu_layer)
                elif isinstance(
                    module, (nn.ConstantPad1d, nn.ConstantPad2d, nn.ConstantPad3d)
                ):
                    pad_layer = PadLayer(node, module)
                    self.node_post_process(pad_layer)
                elif isinstance(module, (nn.ReflectionPad1d, nn.ReflectionPad2d)):
                    pad_layer = PadLayer(node, module)
                    self.node_post_process(pad_layer)
                elif isinstance(module, (nn.ReplicationPad1d, nn.ReplicationPad2d)):
                    pad_layer = PadLayer(node, module)
                    self.node_post_process(pad_layer)
                elif isinstance(module, nn.SELU):
                    selu_layer = SeluLayer(node, module)
                    self.node_post_process(selu_layer)
                elif isinstance(module, nn.ELU):
                    elu_layer = EluLayer(node, module)
                    self.node_post_process(elu_layer)
                elif isinstance(module, nn.Sigmoid):
                    sigmoid_layer = SigmoidLayer(node, module)
                    self.node_post_process(sigmoid_layer)
                elif isinstance(module, nn.Softmax):
                    softmax_layer = SoftmaxLayer(node, module)
                    self.node_post_process(softmax_layer)
                elif isinstance(module, nn.Softplus):
                    layer = SoftplusLayer(node, module)
                    self.node_post_process(layer)
                else:
                    raise NotImplementedError("module %s is not implemented" % (module))
            elif node.op == "call_function":
                function_name = get_function_name(node.target)
                if function_name == "relu":
                    relu_layer = ReluFunc(node)
                    self.node_post_process(relu_layer)
                elif function_name == "add":
                    add_layer = AddFunc(node)
                    self.node_post_process(add_layer)
                elif function_name == "flatten":
                    flatten_layer = FlattenFunc(node)
                    self.node_post_process(flatten_layer)
                elif function_name == "cat":
                    concat_layer = ConcatFunc(node)
                    self.node_post_process(concat_layer)
                elif (
                    function_name == "adaptive_avg_pool2d"
                    or function_name == "adaptive_avg_pool1d"
                ):
                    pooling_layer = PoolingFunc(node)
                    self.node_post_process(pooling_layer)
                elif function_name == "hardsigmoid":
                    hardsigmoid_layer = HardsigmoidFunc(node)
                    self.node_post_process(hardsigmoid_layer)
                elif function_name == "mul":
                    mul_layer = MulFunc(node)
                    self.node_post_process(mul_layer)
                elif function_name == "getitem":
                    getitem_layer = GetItemFunc(node)
                    self.node_post_process(getitem_layer)
                elif function_name == "floordiv":
                    pass
                elif function_name == "transpose":
                    transpose_layer = TransposeFunc(node)
                    self.node_post_process(transpose_layer)
                elif function_name == "prelu":
                    prelu_layer = PReluFunc(node, auto_gen=False)
                    prelu_layer.add_bottom_top()
                    params_prelu = self.model.weight.detach().numpy()
                    prelu_layer.generate_params(params_prelu)
                    prelu_layer.generate_node()
                    self.node_post_process(prelu_layer)
                elif function_name == "hardtanh":
                    clip_layer = ClipFunc(node, auto_gen=False)
                    clip_layer.add_bottom_top()
                    params_clip = [
                        np.array(node.kwargs["min_val"]),
                        np.array(node.kwargs["max_val"]),
                    ]
                    clip_layer.generate_params(params_clip)
                    clip_layer.generate_node()
                    self.node_post_process(clip_layer)
                elif function_name == "leaky_relu":
                    leakyrelu_layer = LeakyReluFunc(node)
                    self.node_post_process(leakyrelu_layer)
                elif function_name == "sigmoid":
                    sigmoid_layer = SigmoidFunc(node)
                    self.node_post_process(sigmoid_layer)
                elif function_name == "softmax":
                    softmax_layer = SoftmaxFunc(node)
                    self.node_post_process(softmax_layer)
                elif function_name == "hardswish":
                    hardswish_layer = HardswishFunc(node)
                    self.node_post_process(hardswish_layer)
                elif function_name == "conv2d":
                    conv_layer = ConvFunc(node, auto_gen=False)
                    conv_layer.add_bottom_top()
                    weight_node = node.args[1]
                    bias_node = node.args[2]
                    weight = getattr(self.model, weight_node.target).detach().numpy()
                    if bias_node is not None:
                        bias = getattr(self.model, bias_node.target).detach().numpy()
                        params_conv = [weight, bias]
                    else:
                        params_conv = [weight]
                    conv_layer.generate_params(params_conv)
                    conv_layer.generate_node()
                    self.node_post_process(conv_layer)
                elif function_name == "linear":
                    gemm_layer = GemmFunc(node, auto_gen=False)
                    gemm_layer.add_bottom_top()
                    weight_node = node.args[1]
                    bias_node = node.kwargs["bias"]
                    weight = getattr(self.model, weight_node.target).detach().numpy()
                    if bias_node is not None:
                        bias = getattr(self.model, bias_node.target).detach().numpy()
                        params_linear = [weight, bias]
                    else:
                        params_linear = [weight]
                    gemm_layer.generate_params(params_linear)
                    gemm_layer.generate_node()
                    self.node_post_process(gemm_layer)
                elif function_name == "avg_pool2d" or function_name == "avg_pool1d":
                    avgpool_layer = AvgPoolFunc(node)
                    self.node_post_process(avgpool_layer)
                elif function_name == "chunk":
                    chunk_layer = ChunkFunc(node)
                    self.node_post_process(chunk_layer)
                elif function_name == "split":
                    split_layer = SplitFunc(node)
                    self.node_post_process(split_layer)
                elif function_name == "getattr":
                    pass
                elif function_name == "boolean_dispatch":
                    if "max_pool2d" in node.name or "max_pool1d" in node.name:
                        pooling_layer = PoolingFunc(node)
                        self.node_post_process(pooling_layer)
                    else:
                        raise NotImplementedError(
                            "function %s is not implemented" % (node.name)
                        )
                elif function_name == "relu6":
                    relu6_layer = Relu6Func(node)
                    self.node_post_process(relu6_layer)
                elif function_name == "max":
                    max_layer = MaxFunc(node)
                    self.node_post_process(max_layer)
                elif function_name == "exp":
                    exp_layer = ExpFunc(node)
                    self.node_post_process(exp_layer)
                elif function_name == "log":
                    log_layer = LogFunc(node)
                    self.node_post_process(log_layer)
                elif function_name == "min":
                    min_layer = MinFunc(node)
                    self.node_post_process(min_layer)
                elif function_name == "elu":
                    elu_layer = EluFunc(node)
                    self.node_post_process(elu_layer)
                elif function_name == "selu":
                    selu_layer = SeluFunc(node)
                    self.node_post_process(selu_layer)
                elif function_name == "abs":
                    abs_layer = AbsFunc(node)
                    self.node_post_process(abs_layer)
                elif function_name == "sqrt":
                    sqrt_layer = SqrtFunc(node)
                    self.node_post_process(sqrt_layer)
                elif function_name == "pow":
                    pow_layer = PowerFunc(node)
                    self.node_post_process(pow_layer)
                elif function_name == "sin":
                    sin_layer = SineFunc(node)
                    self.node_post_process(sin_layer)
                elif function_name == "cos":
                    cos_layer = CosineFunc(node)
                    self.node_post_process(cos_layer)
                elif function_name == "celu":
                    celu_layer = CeluFunc(node)
                    self.node_post_process(celu_layer)
                elif function_name == "sum":
                    sum_layer = SumFunc(node)
                    self.node_post_process(sum_layer)
                elif function_name == "neg":
                    neg_layer = NegFunc(node)
                    self.node_post_process(neg_layer)
                elif function_name == "tanh":
                    tanh_layer = TanhFunc(node)
                    self.node_post_process(tanh_layer)
                elif function_name == "mean":
                    mean_layer = MeanFunc(node)
                    self.node_post_process(mean_layer)
                elif function_name == "sub":
                    sub_layer = SubFunc(node)
                    self.node_post_process(sub_layer)
                elif function_name == "div":
                    div_layer = DivFunc(node)
                    self.node_post_process(div_layer)
                elif function_name == "matmul" or function_name == "bmm":
                    matmul_layer = MatmulFunc(node)
                    self.node_post_process(matmul_layer)
                elif function_name == "softplus":
                    softplus_layer = SoftplusFunc(node)
                    self.node_post_process(softplus_layer)
                elif function_name == "interpolate":
                    upsample_layer = UpsampleFunc(node)
                    self.node_post_process(upsample_layer)
                elif function_name == "_pad":
                    pad_layer = PadFunc(node)
                    self.node_post_process(pad_layer)
                elif function_name == "tile":
                    tile_layer = TileFunc(node)
                    self.node_post_process(tile_layer)
                elif function_name == "normalize":
                    normalize_layer = NormalizeFunc(node)
                    self.node_post_process(normalize_layer)
                elif function_name == "clamp":
                    clip_layer = ClipFunc(node, auto_gen=False)
                    clip_layer.add_bottom_top()
                    params_clip = [
                        np.array(node.kwargs["min"]),
                        np.array(node.kwargs["max"]),
                    ]
                    clip_layer.generate_params(params_clip)
                    clip_layer.generate_node()
                    self.node_post_process(clip_layer)
                elif function_name == "reshape":
                    reshape_layer = ReshapeFunc(node)
                    self.node_post_process(reshape_layer)
                else:
                    raise NotImplementedError(
                        "function %s is not implemented" % (function_name)
                    )
            elif node.op == "call_method":
                if str(node.target) == "size":
                    pass
                elif str(node.target) == "view":
                    reshape_layer = ReshapeFunc(node)
                    self.node_post_process(reshape_layer)
                elif str(node.target) == "reshape":
                    reshape_layer = ReshapeFunc(node)
                    self.node_post_process(reshape_layer)
                elif str(node.target) == "contiguous":
                    pass
                elif str(node.target) == "chunk":
                    chunk_layer = ChunkFunc(node)
                    self.node_post_process(chunk_layer)
                elif str(node.target) == "mean":
                    mean_layer = MeanFunc(node)
                    self.node_post_process(mean_layer)
                elif str(node.target) == "permute":
                    permute_layer = PermuteFunc(node)
                    self.node_post_process(permute_layer)
                elif str(node.target) == "sigmoid":
                    sigmoid_layer = SigmoidFunc(node)
                    self.node_post_process(sigmoid_layer)
                elif str(node.target) == "tanh":
                    tanh_layer = TanhFunc(node)
                    self.node_post_process(tanh_layer)
                elif str(node.target) == "repeat":
                    tile_layer = TileFunc(node)
                    self.node_post_process(tile_layer)
                elif str(node.target) == "unsqueeze":
                    unsqueeze_layer = UnsqueezeFunc(node)
                    self.node_post_process(unsqueeze_layer)
                elif str(node.target) == "squeeze":
                    squeeze_layer = SqueezeFunc(node)
                    self.node_post_process(squeeze_layer)
                elif str(node.target) == "cos":
                    cos_layer = CosineFunc(node)
                    self.node_post_process(cos_layer)
                elif str(node.target) == "pow":
                    pow_layer = PowerFunc(node)
                    self.node_post_process(pow_layer)
                elif str(node.target) == "sin":
                    sin_layer = SineFunc(node)
                    self.node_post_process(sin_layer)
                elif str(node.target) == "abs":
                    abs_layer = AbsFunc(node)
                    self.node_post_process(abs_layer)
                elif str(node.target) == "log":
                    log_layer = LogFunc(node)
                    self.node_post_process(log_layer)
                elif str(node.target) == "sqrt":
                    sqrt_layer = SqrtFunc(node)
                    self.node_post_process(sqrt_layer)
                elif str(node.target) == "transpose":
                    transpose_layer = TransposeFunc(node)
                    self.node_post_process(transpose_layer)
                else:
                    raise NotImplementedError(
                        "method %s is not implemented" % (str(node.target))
                    )
            elif node.op == "output":
                output_layer = OutputLayer(node)
                self.node_post_process(output_layer)
            elif node.op == "get_attr":
                pass
            else:
                raise NotImplementedError("op type %s is not implemented" % (node.op))

    def save(self, dest_path):
        self.dest_path = dest_path
        graph_def = helper.make_graph(
            self.nodes,
            dest_path,
            self.in_tensor_value_info,
            self.out_tensor_value_info,
            self.init_tensor,
            value_info=self.value_info,
        )
        self.model_def = helper.make_model(graph_def, producer_name="pytorch")
        self.freeze()
        self.model_def = optimize_model(self.model_def)
        checker.check_model(self.model_def)
        logger.info("onnx model conversion completed")
        save(self.model_def, dest_path)
        logger.info("onnx model saved to {}".format(dest_path))

    def check_result(self):
        self.pyotrch_inference()
        self.onnx_inference()
        pytorch_output_list = map_reduce(self.pytorch_output, gen_numpy_data)
        assert len(pytorch_output_list) == len(
            self.onnx_output
        ), "pytorch_output: %d vs onnx_output %d" % (
            len(pytorch_output_list),
            len(self.onnx_output),
        )

        for idx in range(len(self.onnx_output)):
            np.testing.assert_allclose(
                pytorch_output_list[idx],
                self.onnx_output[idx],
                rtol=1e-7,
                atol=1e-3,
            )
        logger.info("accuracy test passed")

    def pyotrch_inference(self):
        self.dummy_input = map_replace(self.input_shape, gen_torch_tensor)
        with torch.no_grad():
            if self.concrete_args is not None:
                self.pytorch_output = self.model(
                    *self.dummy_input, **self.concrete_args
                )
            else:
                self.pytorch_output = self.model(*self.dummy_input)

        if isinstance(self.pytorch_output, torch.Tensor):
            self.pytorch_output = [self.pytorch_output]

    def get_onnx_input(self, sess, dummy_inputs):
        dummy_input_list = map_reduce(dummy_inputs, gen_numpy_data)
        onnx_rt_dict = {}
        for idx in range(len(dummy_input_list)):
            onnx_rt_dict[sess.get_inputs()[idx].name] = dummy_input_list[idx]

        return onnx_rt_dict

    def onnx_inference(self):
        import onnxruntime as rt

        sess_options = rt.SessionOptions()
        sess_options.graph_optimization_level = (
            rt.GraphOptimizationLevel.ORT_DISABLE_ALL
        )
        sess = rt.InferenceSession(self.dest_path, sess_options)
        onnx_rt_dict = self.get_onnx_input(sess, self.dummy_input)

        onnx_outname = [output.name for output in sess.get_outputs()]
        self.onnx_output = sess.run(onnx_outname, onnx_rt_dict)

    def export_onnx(self, name, opset_version=13):
        self.dummy_input = map_replace(self.input_shape, gen_torch_tensor)
        torch.onnx.export(
            self.model,
            tuple(self.dummy_input),
            name,
            opset_version=opset_version,
            enable_onnx_checker=False,
        )

    def node_post_process(self, onnx_layer):
        if onnx_layer._node:
            self.nodes.extend(onnx_layer._node)
        self.in_tensor_value_info.extend(onnx_layer._in_tensor_value_info)
        self.out_tensor_value_info.extend(onnx_layer._out_tensor_value_info)
        self.init_tensor.extend(onnx_layer._init_tensor)
        self.value_info.extend(onnx_layer._value_info)

    def freeze(self):
        logger.info("removing not constant initializers from model")
        inputs = self.model_def.graph.input
        name_to_input = {}
        for input in inputs:
            name_to_input[input.name] = input

        for initializer in self.model_def.graph.initializer:
            if initializer.name in name_to_input:
                inputs.remove(name_to_input[initializer.name])
