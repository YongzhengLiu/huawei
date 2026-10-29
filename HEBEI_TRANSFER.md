# 新数据集与替换基础模型

## 两种用途分开

- `reproduce.py`：固定河北复现入口，原数据、原Chronos缓存、原模型尺寸与训练数学保持不变。
- `transfer/`：跨数据集/基础模型接口。新数据/新模型必须重新准备其训练特征和归一化，不能沿用河北缓存并声称复现97.70614%。当前提供契约、可用数据/模型适配器和配置模板；目标数据集的`FeatureBuilder`与`CorrectorRunner`需要接入，模板不冒称已训练的新数据集结果。

## 数据接口

`DatasetProvider.load_fit() -> FitBatch`，`load_query() -> WindowBatch`。`transfer.datasets.NpzWindowDataset`可直接加载两个独立NPZ：

| 字段 | 形状/含义 |
|---|---|
| `issue_time` | `[N] datetime64[m]`，发布时间，唯一 |
| `target_start_time` | `[N]`，`issue_time + score_start * frequency_minutes` |
| `past_target` | `[N,L]`，截至issue前的完整历史，当前接口面向正负荷数据 |
| `past_last_time` | `[N]`，必须严格早于issue |
| `future_known_covariates` | 可选`[N,H,K]`，天气/日历等 |
| `future_covariate_available_at` | 使用未来协变量时必须声明可用时间，默认不得晚于issue |
| `covariate_names` | 可选`[K]`字符串 |
| `future_target` | **只允许出现在fit文件**，`[N,H]`；全H标签必须在首query前成熟 |

query文件禁止包含`future_target/truth/truth96/truth160/query_truth`。评分真值保存在另一文件，只由预测完成后的评分阶段读取。时间统一按`WindowSpec.timezone`约定；适配器负责原始CSV时区、缺失与频率处理，框架不会静默插值或补真值。河北默认`L672/H160/bridge64/tail96/15min`，其他数据集通过`WindowSpec`配置，不写死为102天或40522行。

## 基础模型接口

`ForecastBackend.predict(WindowBatch, WindowSpec) -> ForecastBatch`；返回`point[N,H]`、可选`scene[N,D]`及quantiles。scene维度不固定为768。输入接口没有query标签。

已有适配器：
- `ChronosBoltBackend`：本地Chronos权重、可指定冻结runtime；返回中位数与分位数。Chronos本身不使用未来协变量的事实在metadata中明示，协变量仍可进入后续corrector特征。
- `ExternalNpzBackend`：任何模型都可先导出`issue_time/point/可选scene`，无需修改主流程。
- `LastValueBackend`：仅契约测试，不是研究对照分数。

其他模型实现相同两个方法即可：
```python
class MyForecastBackend:
    def predict(self, batch, spec):
        prediction = my_model(batch.past_target, horizon=spec.horizon)
        return ForecastBatch(point=prediction)
    def fingerprint(self):
        return {"model": "my-model", "weights_sha256": "..."}
```
在JSON中修改`foundation_model.target = "your_module:MyForecastBackend"`。实际工厂为`transfer.pipeline.component(config_section)`。换模型/权重或数据设置会改变`cache_fingerprint`，不得复用旧特征缓存。

## 特征与校正器接口

`FeatureBuilder.fit(fit, base_fit)`仅在fit上计算统计；`transform(windows, base)`支持fit/query；`state_dict()`保存全部归一化及schema。`CorrectorRunner.fit(features, fit_targets, config)`和`predict(features, base)`隔离训练器。请在数据集适配器中声明输入列、条件列、state列及H对应关系，而非把河北的2825/2813维硬套给新数据。

`transfer.temporal.temporal_order(issue_time, seed, epoch, batch_size)`直接调用原采样器操作，支持其他样本数及batch，保证每轮全覆盖一次；若声称使用本方法，应保留该采样操作。模型维度/目标定义变化属于迁移配置，不计作河北固定复现。

使用`configs/transfer.example.json`与`configs/external_model.example.json`作为模板。配置明确区分dataset、foundation_model、feature_builder、corrector、window和输出位置，原冻结入口不读取这些迁移覆盖项。

## 契约测试
```bash
python tests/test_transfer_contracts.py
```
测试其他history/horizon/frequency/scene维度、fit统计不受query影响、future load/未可用天气拒绝、query标签隔离、基础模型替换后的cache key变化，以及其他行数的原采样器全覆盖。仅小型合成数据/LastValue适配器，无真实模型拟合或新质量分数。
