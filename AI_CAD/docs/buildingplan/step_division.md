这一步负责将之前的skill继续迭代升级，向 /home/cyvol0521/.code/gaiahub/CADapi/IFC_front/AI_IFC/docs/internal/architecture/ai-bim-agent-page.md的预期进行进一步的靠近，那么这个就可以参考/home/cyvol0521/.code/gaiahub/CADapi/IFC_front/AI_IFC/AI_CAD/resource/aiblueprint/skills/apex这个skill示例的写法进行下一步的升级改进，将这个skill拆分成明确的执行步骤，框定执行流程

大致需要这么几步
step0: 对齐plan产生的计划文档，主要是read加思考怎么落盘到执行，那么这个其实是要求到 设计这个建筑设计方案的plan结构是什么样子的
step1: 模型自身草拟building_type,采取的设计标准如平面面积，房间具体划分等等，
step2: 与用户交互确认，按照用户的最终意图来
step3：开始构建
step4: 按照指定格式输出到指定位置，这个的话应该是包含两项，一个就是产出的各个DXF图纸的位置，一个就是结构化的fixtures JSON新界结构表，比如框定第几到第几层对应的是哪里存储的DXF图纸，以及DXF不能包含的建筑信息

