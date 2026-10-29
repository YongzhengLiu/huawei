# 河北日前负荷预测：时间分层批次方法复现包

记录结果：seed42，全2026-01-01至2026-04-12共102天 meanDailyKPIE = **97.70614386020668%**。同seed原WPAIR为97.67919128074351%，gain +0.02695257946319745个百分点。三个34天块：98.1504704839164 / 97.06630086963425 / 97.90166022706947。

## 预测与评估口径
前一天08:00发布，使用截止发布时间的672点历史，预测完整160步；前64步仅桥接，评分仅使用索引64:160共96点。查询真值不进入训练、归一化、风险更新或校准。102天已用于配置选择，不能称独立盲测。未来天气沿用原Perfect-weather设定。

## 取得完整文件
仓库根目录的 `download_hebei_repro.py` 会校验代码ZIP和Release数据/模型附件的SHA256并安全解包。默认工作目录为`hebei_repro`。总原始数据约1.50GB、压缩附件约1.20GB。

```bash
python download_hebei_repro.py --workdir hebei_repro
```

## 1. 重放已记录模型与分数（只需NumPy）
```bash
python -m pip install -r hebei_repro/requirements-replay.txt
python hebei_repro/reproduce.py verify
python hebei_repro/reproduce.py replay --seed 42 --output replay42
```
已实际执行：2071个附件文件全SHA、完整102×160 Level/Shape/FiLM网络的独立NumPy重放、160步decoder、102个日期及逐日KPIE，复现97.70614386020668%。网络float64重放与原float32框架数值存在原预锁容差内差异；报告保留误差，不冒称逐位相同。最终记录分数对完整网络核验通过后的原issued预测重新计算。

## 2. 从冻结训练输入重训完整96轮
使用Linux、Python3.11、Torch2.0.1+cu118、NumPy1.24.1、CPU8。其他CPU/BLAS版本可能产生浮点差异，不保证任意机器逐位一致。
```bash
python3.11 -m venv .venv-training
.venv-training/bin/pip install -r hebei_repro/requirements-training.txt
.venv-training/bin/python hebei_repro/reproduce.py train --seed 42 --output retrain42
```
此入口使用全部40522条冻结输入/标签，不重新拟合或替换特征；完整96轮、15264次AdamW更新、65..96共32轮参数平均、完整102×160预测、原mask/RNG/PhaseYearWeights/risk/D2/clip不改。原训练完整优化片段以及模型构造、采样、输入装配、预测和decoder以逐函数AST/逐文件字节方式保留；见`PORTABILITY_EQUIVALENCE.json`。仅文件根目录、环境检查、输出权限与机器成本审计被分离。移植入口尚未声称完成一次新的96轮端到端重训验证；原真实训练结果与完整源码/检查点同时提供，不能把AST检查当新拟合实测。

运行会拒绝覆盖已有输出目录。`train`结束后先完整网络/decoder核验再读取评分真值；评分结果写`REPRODUCTION_RESULT.json`和`DAILY_KPIE.csv`。

## 方法
按训练发布时间排序，将40522条样本分成256个连续时间段，74段159条、其余158条。每轮仍只用原rng.permutation生成一次随机排列，按其rank安排各段内部顺序，每个完整batch从每段取一条；158个256条batch和最后74条，所有样本每轮恰好一次。模型2509761参数，其余训练与推理沿用原WPAIR。

## 文件结构
- `reproduce.py`：完整校验/重放/重训/评分入口。
- `repro/`：可移植模型、原生损失、采样器、完整训练循环和独立网络核查器。
- `original_snapshot/`：Release附件解包后得到。包含全部冻结训练输入、归一化、时钟/年份权重、查询与control、实际检查点和issued预测、Bolt权重及冻结运行时、原天气CSV、原源代码及原机成本审计文件。
- `PAYLOAD_MANIFEST.json`：附件全部2071文件的逻辑路径、大小、SHA和角色。
- `metadata/`、`verified_results/`：原协议/实施锁/结果和已执行的重放报告。
- `environments/`：原训练及部署环境的Python/发行版版本记录。

冻结输入复现不声称已实现从原始电表数据到全部历史FM缓存的重新构建；缓存作为实际训练数据完整提供。原机训练/部署成本报告是历史测量，不是任意新机器耗时承诺。

## 三种子状态
当前仅seed42结果已完成。用户要求的seed43/44补充确认正在独立串行跟进；未完成前不编造三种子平均，也不以平均预测替代三个单模型分数。

## 第三方文件
Bolt配置记录来源为autogluon/chronos-bolt-base。冻结运行时的Chronos、Transformers等原许可证和版本文件随附件保留；第三方文件遵循各自原许可。包内不包含账户凭据、SSH私钥或GitHub令牌。

## 迁移到其他数据集与替换Chronos

数据集、基础模型、特征构建和校正器使用独立接口，见`TRANSFER.md`与`configs/transfer.example.json`。已提供NPZ数据适配器、Chronos Bolt适配器、外部预测适配器及原时间分层采样器接口；history/horizon/频率/scene维度可配置。目标数据集的特征构建和校正器需要按接口接入，不宣称已在新数据集训练验证。

```bash
python hebei_repro/tests/test_transfer_contracts.py
```
合成接口检查已通过：不同窗口/维度、fit-only统计、因果时间检查、query标签隔离和基础模型替换后缓存失效。固定河北入口不读取迁移覆盖配置。
