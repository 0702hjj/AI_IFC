# 发布流程

## skill 发布（手工 runbook）

每个 skill 独立版本化（语义化版本，`SKILL.md` frontmatter 的 `version` 字段），归档命名 `<name>-<version>.tar.gz`。发布一个 skill 的步骤：

1. **bump**：改对应 skill `SKILL.md` 的 `version`，并在包内 `CHANGELOG.md` 追加版本条目。
2. **打包**：

   ```bash
   python tools/skill_pack.py --skill <name> --archive
   # aidxfv3 / aiplan 需要显式指定目录：
   python tools/skill_pack.py --skill aidxfv3 --skill-dir skills/aidxfv/v3 --archive
   ```

   产物在 `skills/dist/`。

3. **校验**：`python -m pytest tests/skill/ -q` 全绿（含打包产物结构与 frontmatter 契约测试）。
4. **发布**：

   ```bash
   git tag skill-<name>-<version>
   gh release create skill-<name>-<version> skills/dist/<name>-<version>.tar.gz
   ```

当前仅手工 runbook，CI 自动化（打 tag 即发布）本轮未做。

## 平台发布

平台整体版本（v0.1.0 等）的发布实践：功能在迭代分支累积 → PR 合入 main（CI 全绿）→ 更新 [更新日志](/project/changelog.md) → 打 `v<version>` tag 并建 GitHub Release。平台各组件（web / server / converter / services/ifc）共用同一仓库与同一版本号，skill 则用独立的 `skill-<name>-<version>` tag 单独发布，与平台版本解耦。
