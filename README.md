# COL-Trees: Efficient Hierarchical Object Search in Road Networks

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2601.22183"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2601.22183-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2601.22183](https://arxiv.org/abs/2601.22183) |

## Summary

The COL-Tree paper addresses the problem of efficiently answering spatial queries for Points of Interest (POIs) on large-scale road networks, specifically three query types: Aggregate k Nearest Neighbors (AkNN), k Farthest Neighbors (kFN), and range queries. The core challenge is that these queries require computing network distances (shortest paths) on graphs with tens of millions of vertices, making naive approaches prohibitively slow.

## Run it

```bash
pip install sciworld
sw research 2601.22183 --mode innovate --agent claude-code
sw evaluate 2601.22183
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

