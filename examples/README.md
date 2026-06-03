# Demo Tasks

这些任务用于展示 Forge Agent 的 `run --task-file` 能力。

## 修复 quicksort

```bash
agent run --repo . --task-file examples/tasks/fix_quicksort.md
```

如果 console script 不可用，可以使用：

```bash
python -m entry.cli run --repo . --task-file examples/tasks/fix_quicksort.md
```

## 为 linked list 补充测试

```bash
agent run --repo . --task-file examples/tasks/add_linked_list_tests.md
```

如果 console script 不可用，可以使用：

```bash
python -m entry.cli run --repo . --task-file examples/tasks/add_linked_list_tests.md
```
