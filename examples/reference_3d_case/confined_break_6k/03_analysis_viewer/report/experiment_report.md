# PFC 科研可视化实验结果

- 实验：run_case17_confined_break_6k_r1
- 数据边界：`REAL_PFC`
- 标准化输入契约：`pfc.standardized-experiment@1.0.0`
- 输入契约 SHA-256：`fed3575072f9820818670f43cdeb80b79bf294606f91edaacb08e0fd6402375b`
- 验证状态：`NOT_VERIFIED`
- 生成时间：2026-11-24T13:03:06+00:00

## 实际生成

- `03_analysis/analysis.json`
- `03_analysis/chart_specs.json`
- `03_analysis/chart_decisions.json`
- `03_analysis/chart_decision_record.json`
- `03_analysis/display_data.json`
- `03_analysis/data_layers.json`
- `04_viewer/scientific_viewer.html`
- `04_viewer/viewer/`
- `04_viewer/data/`
- `04_viewer/linkage_decisions.json`
- `04_viewer/viewer_manifest.json`
- `05_charts/chart_specs.json`
- `06_publication_figures/figure_plan.json`
- `07_metadata/source_contract.json`
- `07_metadata/experiment_capabilities.json`
- `07_metadata/output_contract.json`
- `07_metadata/output_index.json`
- `report/experiment_report.md`

## 未生成或未验证

- Viewer 未进行浏览器运行验收。
- 本章节不包含真实 PFC 求解或实验验证结果。
- 没有输入数据的物理量、图表和图片不会被补齐或伪造。
- 本次没有执行单元测试、集成测试或性能测试。

## 真实性与边界

- 原始采集、质量检查和标准化由 pfc-headless 管理。
- 本结果只读消费标准化契约，不复制或修改其原始数据与数组。
- 本结果只在独立输出目录写分析、图表和视觉产物。
- 标准化数组使用变长实体偏移，不假设固定颗粒数。
- 派生量记录公式、输入、单位、来源和适用条件。
- 播放与时间轴只切换真实采样帧，不插值。

## 文件索引

参见 `07_metadata/output_index.json`。

## 图表未生成原因

- `case_17:line_load_time`: `NOT_CAPTURED` — No valid PFC2D line-load channel exists; the temporal line-load chart is omitted.
- `case_17:line_load_strain`: `NOT_CAPTURED` — Both valid PFC2D line load and strain are required for the mechanical-response path.
- `experiment:case_comparison`: `NOT_GENERATED` — A comparison requires at least two cases.

## 数据能力摘要

- `ball_position`: `SUPPORTED`
- `ball_radius`: `SUPPORTED`
- `wall_geometry`: `SUPPORTED`
- `fracture_event`: `SUPPORTED`
- `contact_network`: `NOT_CAPTURED`
- `bond_network`: `NOT_CAPTURED`
- `particle_displacement`: `SUPPORTED`
- `particle_speed`: `SUPPORTED`
- `particle_acceleration`: `SUPPORTED`
- `nominal_stress`: `SUPPORTED`
- `line_load`: `NOT_CAPTURED`
