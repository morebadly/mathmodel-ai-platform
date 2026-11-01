# 素材与字体说明

| 素材 | 来源与用途 |
| --- | --- |
| `assets/association-logo.png` | 用户已有的协会高清会标原图，未重绘；仅随本项目设计交付保留。本 PR 不另行授予会标的商标或第三方素材权利。 |
| `assets/campus-watercolor-v1.png` | 2026-10-31使用内置图像生成工具，参考用户提供的B版草图复原。用户已确认使用；属于校园概念装饰，不是学校官方插画，也不应作为建筑测绘资料。 |
| `assets/campus.svg` | 早期简化校园概念素材。基础样式仍有引用；当前由 `campus-revision.css` 的水彩素材覆盖。 |
| `preference-controls.js` 内的SVG | 页面内太阳、月亮、电脑及方向箭头图标，随独立原型提供，不修改原会标。 |

水彩构图保留中轴主楼、两侧建筑、水彩树木、水面、淡金与深蓝色调，以及数学符号和几何线；不包含网页标题、旧产品名或按钮。首页使用完整构图，内部工作页降低装饰强度。

字体使用CSS系统回退链：标题为Georgia、Noto Serif SC、Source Han Serif SC、SimSun及通用衬线字体；正文为Arial、Noto Sans SC、Microsoft YaHei及通用无衬线字体。本 PR 未附字体二进制，也未增加外部字体下载。不同电脑的字形和换行可能不同，正式接入需检查中英俄显示。
