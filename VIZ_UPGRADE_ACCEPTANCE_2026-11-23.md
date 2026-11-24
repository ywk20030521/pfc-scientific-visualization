# 可视化技能 2D/3D 渲染与布局升级验收报告（2026-11-23）

依据：`_practice/viz_upgrade_proposal/技术报告-2D3D渲染与布局升级方案.md`
备份：`_practice/skill_backup_20261123_vizimplement/`

## 1. 已落地改动

- **three r160**：`assets/vendor/three.min.js` 为 `three@0.160.0` 核心 + OrbitControls 的全局 IIFE 打包；`OrbitControls.js` 为占位。浏览器实测 `THREE.REVISION=160`、`THREE.OrbitControls=function`。
- **布局**：`#shell` 改为黄金分割比 `1.618fr : 1fr`；所有 Three.js 控件迁入 `#stage` 底部横向控制坞，默认折叠；模拟摘要按后续反馈放在控制坞“视图设置”下方；深色模式与 `?theme=dark` 彻底移除；右栏只剩图表。
- **控制坞交互**：`#dockToggle` 切换 `collapsed` 与 `body.dataset.dock`，并触发 `resize`。浏览器实测 `collapsed → open → collapsed` 正常，折叠时剖面 inset 回到底部 44px，展开时被顶起避让。控制坞展开高度固定为 36vh，指标/时间/定位行固定最小高度，播放 8 次采样中 `top=598px, height=360px` 恒定，消除抖动。
- **渲染**：浅色预设启用 ACES（曝光 1.06）、`MeshPhysicalMaterial`（roughness 0.30 / clearcoat 0.34 / envMapIntensity 1.4）、提亮后的光照与 Canvas equirect 环境图、确定性 glint（1.00–1.12）。默认 Nature ramp 升级为已验证的亮色阶；高对比色阶可通过 `#colorPalette` 切换。
- **2D inset**：由当前真实帧直接绘制，俯视与剖面按维度/图表元数据智能取舍；`body.dataset.insetChoice` 记录 `both|top|section`。PFC3D 实测 `section`，PFC2D 实测 `top`。修正了 `choice=section` 时剖面画布未绘制的分支错误；切片不足时回退为投影并改标题。
- **取景补偿**：控制坞展开时按相机上方向平移 target/camera，而不是用 `setViewOffset` 缩放画面；折叠时自动撤销。

## 2. 验收结果

- 单元测试：`PYTHONPATH=scripts python -m unittest discover -s tests -q` → **71 tests, OK**。
- 浏览器验收（真实 PFC3D `run_case06_rock_ucs_r2`、PFC2D `run_case06_rock_ucs_r8`）：
  - `body[data-ready=1]`，`__PFC_VIEWER_ERROR__` 为空，无 pageerror；
  - `#panel` 中按钮/输入框/下拉框数量 = 0；
  - 新增 ID 全部存在；`themeToggle` 不存在；
  - 折叠/展开、色阶切换、inset 决策均正常。
- 截图（最终保留）：`render-3d-latest.png`、`render-2d-latest.png`（早期 `verify-upgraded-*.png`、`fix-verified-*.png`、`fullcap-*.png` 已清理）。

## 3. §10 实测漏洞处理说明

1. **摘要与深色模式**：摘要已移到原深色按钮位置；深色模式已删除；控制坞收起/展开已在真实浏览器验证通过。
2. **墙体/接触/键/inset**：
   - 墙体数据契约当前只提供墙顶点折线。现已把每段折线拉伸为 `InstancedMesh` 实体细杆（半径按域尺度、半透明蓝色），并保留轮廓线与顶点点，视觉上不再是单像素折线；但这仍不是上游三角面墙实体。若要真实墙面，需采集器输出墙面三角面/法向数据。
   - 接触与键在本次案例中 `entityStatus.contact/bond = NOT_CAPTURED`，因此控件禁用并标记“未采集”，这是正确的科研数据边界，不是渲染 bug。
   - 早期 mock 中俯视/剖面看起来一致，是因为 inset 使用了静态初始帧且投影轴选择不当；现已改为当前帧驱动，并按最小域轴确定俯视法向、按另一轴确定剖面，PFC2D 因 Z 厚度近零只保留一个 inset。
3. **颗粒渲染**：v2 参数已写入技能；收起后剖面 inset 回到左下角 44px，展开时被顶起避让。
4. **网页单独分享**：viewer 是“HTML + viewer/ + data/”目录，只发 HTML 会缺 vendor 与帧数据，打不开。用打包脚本生成 ZIP 即可离线分享：
   `python scripts/viewer/package_viewer.py <viewer_root> <out.zip>`
   实测 231 个文件、36.6 MB → 19.1 MB ZIP。解压后双击 `scientific_viewer.html` 即可。不建议把数据 base64 内嵌单 HTML：3D 案例 36 MB 会膨胀到约 49 MB 且解析内存占用高。若需要链接分享，可把该目录作为静态站点发布，数据仍按需加载。

## 4. 边界

- 未改变数据契约、帧选择语义、图表智能选型与导出契约。
- 墙体实体面、接触/键真实网络仍受上游采集限制；报告与矩阵中均显式标注。

## 5. 第二轮 bug 修复（同日，基于 headless 真实数据契约核对）

按用户 5 点反馈 + headless-skill 实际交付字段核对后修复：

1. **模拟摘要直接展示**：`#summaryInline` 由 `<details>/<summary>` 折叠改为始终展开的 `<div>`，无按钮；仍位于控制坞“视图设置”下方，`#summaryBody` 保持供报告渲染。
2. **裂纹随颗粒动态变化**：裂纹记录扩展为 11 字段，末尾两位为可选端点 Ball ID。viewer 的 `updateCracks()` 每帧用当前帧 Ball 坐标重算裂纹中点（保留断裂方向/长度）。无端点 ID 的真实采集退化为静态坐标，向后兼容。
3. **2D 不显示剖切与俯视/剖面 inset**：`body[data-dimension="2"]` 通过 CSS 隐藏 `.dim3-only` 控件（剖切开关、剖切轴/位置、二维缩略图开关）与所有 `.scene-inset`；`drawInsets()` 在 2D 直接返回并把 `insetChoice` 置为 `none`。浏览器实测 2D 下这些元素全部不可见。
4. **3D 墙体与裂纹**：墙体按 headless 提供的顶点折线逐段拉伸为 `InstancedMesh` 实体杆；MOCK 测试集给出四角压板环，浏览器可见实体压板轮廓。3D 裂纹由测试集的动态裂纹通道验证：后期帧 37 条裂纹可见（19 拉伸 / 18 剪切）。
5. **完整测试数据集（接触 + 键）**：新增 `examples/build_fullcapability_mock.py`，生成严格对齐 headless 契约的 MOCK 标准化包（`examples/standardized_data/FullCapability_Mock/`）：ball/wall/fracture/contact 使用 headless 真实字段，bond 与 fracture 端点 ID 作为**标注的 MOCK 扩展**用于测试 Viewer 能力。经 `standard_contract.verify` PASS、`run_pipeline` 全通道 SUPPORTED，浏览器实测 contact=120 段、bond=120 段、crack=37 条渲染正常。

**修复的真实 bug（契约错配）**：headless converter 实际输出 `contact_offsets`/`contact_end1_id`/`contact_end2_id`/`contact_force_xyz`（矢量力），而 viewer 适配层此前只认 `contact_frame_offsets`/`contact_ball_id_a`/`contact_ball_id_b`/`contact_force_n`（标量力），导致真实项目即使采集了接触网络也无法显示。已修复 `_network_frame_payload()` 同时兼容两套命名（矢量力取模转标量），并新增契约测试锁定该行为。

**headless 契约边界（据实声明）**：真实 headless 交付包**不含**独立 bond 数组、不含 fracture 端点 Ball ID、不含 wall 面片（仅顶点折线）。因此：
- 静态裂纹 = 真实能力；动态裂纹 = 需 headless 扩展 fracture 采集端点 ID 后启用，测试集仅验证代码路径；
- 接触网络 = 真实能力（本次已修复显示）；键网络 = Viewer 预留能力，需上游产出 `bond_*` 数组；
- 墙体 = 基于真实顶点折线的实体杆，不是三角面墙板。

回归：`PYTHONPATH=scripts python -m unittest discover -s tests -q` → **75 tests, OK**。浏览器验收无 pageerror。2D/3D 最终渲染截图：`render-3d-latest.png`、`render-2d-latest.png`（均在 `_practice/viz_upgrade_proposal/`，由 `reshoot_latest.mjs` 生成）。

## 6. 真实 PFC 重采集验证（2026-11-23 晚，itasca-mcp 驱动）

通过 itasca-mcp 真实驱动 PFC2D/PFC3D Console（非 MOCK），验证动态裂纹与接触网络：

**PFC2D（run_case06_fullcap_r4）**
- 真实运行 33.39s，开启 `fracture_observer` + `capture_contacts` + `wall.contact_force`。
- 采集结果：198 条断裂事件带 `ball_id_a/b`，45,975 行接触网络端点为真实 Ball ID（1–125，墙端点 -1）。
- 期间修复 headless `capture_case.py` 两个真实 bug：
  1. fracture CSV 的 `string.build('%10','%11')` 被 FISH 解析为 `%1`+数字，导致坐标列错位 → 改用 `string()` 逐值拼接；
  2. 接触端点用 `type.pointer.id()`（指针地址 1284443565）而非 `ball.id()` → 改用端点 Ball ID 辅助函数，并把该函数移到公共采集 FISH 块。
- 标准化交付 `deliveries/run_case06_fullcap_r4` COMPLETE；viewer `realcap_2d_final`：裂纹端点球屏幕位置随帧移动（x 374→204），contact=88 段，2D 无 inset，无 pageerror。截图 `realcap-2d-final-contacts.png`。

**PFC3D（run_case06_3dfull_r1）**
- 真实运行 89.91s，同样开启 fracture/contact 观测。
- 接触网络真实采集（viewer contact=287 段）；wall 面 SUPPORTED。
- 断裂事件为 0：该 UCS 模型在求解区间内未发生 bond_break（仍在弹性段），是真实物理结果，如实标 `fracture_event=NOT_CAPTURED`，不伪造裂纹。若要验证 3D 动态裂纹，需让模型加载到破裂阶段后重跑。
- 标准化交付 `deliveries/run_case06_3dfull_r1` COMPLETE；viewer `realcap_3d_final` 无报错。截图 `realcap-3d-final.png`。

边界：以上为真实 PFC Console 运行结果；Console 由守护 shell 保活（工具会话约束），MCP 一次只连一个 Bridge URL，2D/3D 分时段在同一 9001 端口完成。

## 7. PFC3D wall 真实面片渲染（2026-11-23 21:20）

**问题**：此前 3D wall 只能画成实体细杆 / Z 折线。经真实引擎探查，根因不在 viewer，而在
上游数据缺失 facet 拓扑：PFC3D 的 `wall generate ... plane` 实际由 2 个三角 facet 组成，
`facet.vertices()` 可返回 3 个顶点 ID + 坐标；但 headless 的 `read_wall_static()` 只存了
facet 的 `id/active/pos/normal`，未存顶点 ID，converter 也只导出 `wall_vertex_xyz` 折线点集。

**修复（headless）**：
- `capture_case.py`：facet 增 `vertex_ids`（来自 `facet.vertices()`）。
- `standardize/legacy.py`：`_static_walls` 保留 facets（含 vertex_ids/normal）。
- `standardize/converter.py`：新增 `wall_facet_id / wall_facet_wall_id / wall_facet_active /
  wall_facet_normal / wall_facet_vertex_offsets / wall_facet_vertex_ids` 六个数组 + channel 元数据，
  向后兼容（无 facet 时为空数组）。
- 新增 `tests/test_wall_facet_contract.py`（3 项）。

**修复（visualization）**：
- `payload_builder.py`：static walls 携带 facets（vertex_ids + normal）。
- `scientific-viewer.js`：新增 `wallFaces` Mesh + `updateWallFaces()`，按当前帧顶点坐标
  重建三角面（双面色、半透明实体材质），showWalls 开关与 dispose 同步；`body.dataset.wallFaces`
  记录三角形数便于验收。无 facet 拓扑时自动回退到杆渲染。

**真实验证**：用双桥直连（9001=3D）重跑 `run_case06_3dfacet_r2`（64.02 s，task facet3d001）：
- 采集 static.json facet 带 `vertex_ids [1,2,3]/[3,2,4]`；NPZ 导出 4 facet / 12 顶点 ID。
- viewer `facet_3d_result`：static.js 含 facets，`wallFaces=4`（2 wall × 2 facet），无 pageerror，
  截图 `facet-3d-wallfaces.png` 显示上下压板为实体半透明平面。
- 旧数据（realcap_3d_final，无 facet）`wallFaces=0`、正常回退、无报错。
- 回归：headless 57 tests OK（含新增 3 项）；visualization 75 tests OK。

## 8. wall 面/杆表达取舍与 3D 真压缩验证（2026-11-23 21:40）

- 修复：有真实 facet 面片时隐藏 wallSolids/wallLines/wallPoints（避免同一 wall 的"面+杆"
  双重表达误导）；showWalls 开关依据 `body.dataset.wallFaces` 决定显示真实面还是回退杆。
- 根因说明（用户三问）：3D case_5 无 wall velocity 指令、用覆盖整个 domain 的 plane wall，
  故 wall 静止且过大——这是模型配置问题，数据是真实的，非渲染 bug。2D case_5 有
  `wall attribute velocity-y`，是真压缩实验。
- 参考 2D 建 `case_10`（finite polygon wall ±0.25 + wall velocity-z），真实采集 90.90 s：
  top wall 顶点 z 0.500→0.475 逐帧下移；viewer `case10_compress_result` wallFaces=4、无细棍、
  无报错。截图 `case10-frame-early.png` / `case10-frame-late.png`。
- 回归：headless 57 / visualization 75 tests OK。

## 9. wall 轮廓化恢复颗粒视觉（2026-11-23 21:55）

- 用户反馈蓝色填充 wall 面遮挡颗粒、有穿模感。核实颗粒参数未变，问题在填充面。
- `wallFaces` 由填充 Mesh 改为 LineSegments 真实 facet 轮廓（顶点来自当前帧真实数据，
  不缩放）；细杆与其共存。颗粒接触恢复上一版清晰度。
- 截图：`facet-3d-outline.png`（case_5 plane wall 真实大轮廓）、`case10-outline.png`
  （finite wall ±0.25 贴合颗粒堆）。
- 回归：visualization 75 tests OK。

并行升级 headless-skill 到 1.1.0：新增 progress-aware watchdog（`run diagnose`），
以 CPU/输出/帧行进展信号区分 RUNNING/STALLED，取代固定超时；headless 63 tests OK。
详见技术报告 §16。

## 10. wall 闭合薄壳 + 接触默认可见（2026-11-23 22:20）

- wallFaces 从轮廓线改为闭合薄壳：用当前帧真实 wall 顶点 + facet 边界环 + 真实法向，
  按 Z 字细棍半径挤出（蓝色透明 opacity 0.22、depthWrite false），逐帧更新、有 facet 时隐藏细棍。
- 接触默认勾选；首帧 Cycle 0 真实无接触（offsets=[0,0,2043,...]），帧 100 显示 1300 段。
- 实测：`realcap_3d_result` wallFaces=24、无报错，截图 `realcap-3d-slab-contacts.png`；
  `case10_slab_check` finite wall 贴合颗粒域、薄层随压缩下移，截图 `case10-slab-early/late.png`。
- headless 按用户要求撤销版本号（SKILL_VERSION 与 SKILL.md metadata.version 均移除），
  watchdog 功能保留。回归：headless 63 / visualization 75 tests OK。
