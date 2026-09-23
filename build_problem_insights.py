from __future__ import annotations

import json
import hashlib
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
KNOWLEDGE_DIR = ROOT
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
RECORDS_PATH = KNOWLEDGE_DIR / "records.json"
OUT_JSON = KNOWLEDGE_DIR / "problem-insights.json"
OUT_BY_TOPIC = KNOWLEDGE_DIR / "problem-insights-by-topic.md"
OUT_BY_PROBLEM = KNOWLEDGE_DIR / "problem-insights-by-problem.md"
OUT_QUALITY = KNOWLEDGE_DIR / "problem-insights-quality-check.md"
AI_GENERATED_PATH = KNOWLEDGE_DIR / "ai-generated-insights.json"

SUMMARY_PLACEHOLDER_PREFIXES = ("待生成", "题面正文缺失", "本地题解正文不足")
MISSING_SOLUTION_STATUSES = {
    "missing_editorial",
    "statement_only_missing_editorial",
    "pending_ai",
}

TOPIC_ORDER = [
    "数论与同余",
    "组合计数与概率",
    "动态规划与状态设计",
    "图论与网络流",
    "树结构",
    "字符串",
    "博弈",
    "数据结构",
    "构造与贪心",
    "几何",
    "代数、矩阵与多项式",
    "交互",
    "基础实现与模拟",
]


@dataclass(frozen=True)
class TopicRule:
    topic: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]


TOPIC_RULES = [
    TopicRule(
        "数论与同余",
        ("number theory", "chinese remainder theorem"),
        ("gcd", "lcm", "modulo", "mod ", "prime", "divisor", "factor", "mobius", "crt", "totient", "phi"),
    ),
    TopicRule(
        "组合计数与概率",
        ("combinatorics", "probabilities"),
        ("count", "ways", "probability", "expected", "binomial", "catalan", "permutation", "inclusion-exclusion"),
    ),
    TopicRule(
        "动态规划与状态设计",
        ("dp", "bitmasks"),
        (" dp", "state", "transition", "mask", "submask", "knapsack", "memo"),
    ),
    TopicRule(
        "图论与网络流",
        ("graphs", "flows", "graph matchings", "shortest paths", "2-sat", "dsu"),
        ("graph", "edge", "vertex", "matching", "flow", "cut", "path", "cycle", "component", "shortest"),
    ),
    TopicRule(
        "树结构",
        ("trees", "dfs and similar"),
        ("tree", "subtree", "ancestor", "dfs", "centroid", "hld", "root"),
    ),
    TopicRule(
        "字符串",
        ("strings", "string suffix structures", "hashing", "expression parsing"),
        ("string", "substring", "prefix", "suffix", "palindrome", "border", "kmp", "lcp"),
    ),
    TopicRule(
        "博弈",
        ("games",),
        ("game", "winning", "losing", "nim", "grundy", "mex", "player"),
    ),
    TopicRule(
        "数据结构",
        ("data structures",),
        ("segment tree", "fenwick", "sparse table", "heap", "set", "treap", "lazy", "query", "update"),
    ),
    TopicRule(
        "构造与贪心",
        ("constructive algorithms", "greedy", "sortings", "two pointers", "binary search", "brute force"),
        ("construct", "greedy", "sort", "binary search", "two pointers", "choose", "minimum", "maximum"),
    ),
    TopicRule(
        "几何",
        ("geometry",),
        ("point", "line", "polygon", "circle", "coordinate", "distance", "grid"),
    ),
    TopicRule(
        "代数、矩阵与多项式",
        ("matrices", "fft"),
        ("matrix", "determinant", "polynomial", "convolution", "fft", "ntt", "linear basis"),
    ),
    TopicRule(
        "交互",
        ("interactive", "communication"),
        ("interactive", "query", "ask", "respond", "judge"),
    ),
]

TRANSLATIONS = [
    ("if there is no", "如果不存在"),
    ("if there are no", "如果不存在"),
    ("there exists", "存在"),
    ("there exist", "存在"),
    ("there are", "有"),
    ("there is", "有"),
    ("the number of", "数量"),
    ("number of", "数量"),
    ("how many", "多少"),
    ("positive integers", "正整数"),
    ("non-negative integers", "非负整数"),
    ("a single integer", "一个整数"),
    ("an integer", "一个整数"),
    ("two integers", "两个整数"),
    ("three integers", "三个整数"),
    ("distinct integers", "不同整数"),
    ("all elements", "所有元素"),
    ("if and only if", "当且仅当"),
    ("at least", "至少"),
    ("at most", "至多"),
    ("is equal to", "等于"),
    ("are equal to", "等于"),
    ("such that", "使得"),
    ("can be", "可以被"),
    ("it is enough", "只需要"),
    ("it is possible", "可行"),
    ("You are given", "给定"),
    ("Given", "给定"),
    ("You are allowed to", "你可以"),
    ("You have", "你有"),
    ("You need to", "需要"),
    ("You have to", "需要"),
    ("Your task is to", "任务是"),
    ("you want to", "你需要"),
    ("wants to know", "想知道"),
    ("would like to", "想要"),
    ("Find", "求"),
    ("Determine", "判断"),
    ("Calculate", "计算"),
    ("Count", "计数"),
    ("Output", "输出"),
    ("Help", "帮助"),
    ("For each", "对每个"),
    ("In other words", "换句话说"),
    ("Without loss of generality", "不失一般性"),
    ("we can", "可以"),
    ("we need", "需要"),
    ("we have", "有"),
    ("we want", "我们要"),
    ("you can", "可以"),
    ("can", "可以"),
    ("must", "必须"),
    ("will", "会"),
    ("it is sufficient", "只需"),
    ("this means", "这意味着"),
    ("notice that", "注意到"),
    ("observe that", "观察到"),
    ("key observation", "关键观察"),
    ("therefore", "因此"),
    ("thus", "因此"),
    ("because", "因为"),
    ("since", "因为"),
    ("instead", "换个角度"),
    ("minimum", "最小"),
    ("maximum", "最大"),
    ("possible", "可行"),
    ("maximize", "最大化"),
    ("minimize", "最小化"),
    ("perform", "执行"),
    ("choose", "选择"),
    ("selected", "被选择"),
    ("array", "数组"),
    ("arrays", "数组"),
    ("sequence", "序列"),
    ("sequences", "序列"),
    ("string", "字符串"),
    ("strings", "字符串"),
    ("tree", "树"),
    ("trees", "树"),
    ("graph", "图"),
    ("graphs", "图"),
    ("permutation", "排列"),
    ("permutations", "排列"),
    ("operation", "操作"),
    ("operations", "操作"),
    ("query", "询问"),
    ("queries", "询问"),
    ("answer", "答案"),
    ("answers", "答案"),
    ("integer", "整数"),
    ("integers", "整数"),
    ("number", "数"),
    ("numbers", "数"),
    ("vertex", "点"),
    ("vertices", "点"),
    ("edge", "边"),
    ("edges", "边"),
    ("path", "路径"),
    ("paths", "路径"),
    ("subtree", "子树"),
    ("modulo", "取模"),
    ("probability", "概率"),
    ("expected", "期望"),
    ("palindrome", "回文"),
    ("palindromes", "回文"),
    ("substring", "子串"),
    ("substrings", "子串"),
    ("subsequence", "子序列"),
    ("subsequences", "子序列"),
    ("binary search", "二分"),
    ("segment tree", "线段树"),
    ("monotonic stack", "单调栈"),
    ("dynamic programming", "动态规划"),
    ("linear sieve", "线性筛"),
    ("lower_bound", "二分查找"),
    ("value", "值"),
    ("values", "值"),
    ("element", "元素"),
    ("elements", "元素"),
    ("condition", "条件"),
    ("conditions", "条件"),
    ("valid", "合法"),
    ("invalid", "非法"),
    ("different", "不同"),
    ("distinct", "不同"),
    ("same", "相同"),
    ("length", "长度"),
    ("size", "大小"),
    ("cost", "代价"),
    ("score", "分数"),
    ("total", "总计"),
    ("prefix", "前缀"),
    ("suffix", "后缀"),
    ("between", "之间"),
    ("among", "之中"),
    ("first", "第一个"),
    ("last", "最后一个"),
    ("next", "下一个"),
    ("previous", "前一个"),
    ("final", "最终"),
    ("initial", "初始"),
    ("only", "只"),
    ("exactly", "恰好"),
    ("every", "每个"),
    ("each", "每个"),
    ("some", "一些"),
    ("other", "其他"),
    ("both", "二者"),
    ("when", "当"),
    ("where", "其中"),
    ("which", "其中"),
    ("what", "什么"),
    ("after", "之后"),
    ("before", "之前"),
    ("than", "比"),
    ("into", "变成"),
    ("over", "遍历"),
    ("order", "顺序"),
    ("following", "下面"),
    ("consider", "考虑"),
    ("using", "使用"),
    ("use", "使用"),
    ("solution", "题解"),
    ("complexity", "复杂度"),
    ("cell", "格子"),
    ("cells", "格子"),
    ("row", "行"),
    ("rows", "行"),
    ("column", "列"),
    ("columns", "列"),
    ("city", "城市"),
    ("cities", "城市"),
    ("point", "点"),
    ("points", "点"),
    ("position", "位置"),
    ("positions", "位置"),
]

EDITORIAL_CUES = (
    "key observation",
    "notice",
    "observe",
    "equivalent",
    "if and only if",
    "necessary",
    "sufficient",
    "it is enough",
    "we only need",
    "we can",
    "the answer is",
    "this means",
    "therefore",
    "thus",
    "because",
    "let ",
    "consider",
    "proof",
    "theorem",
    "claim",
    "key insight",
    "key idea",
)

SOLUTION_CUES = (
    "we can",
    "use",
    "maintain",
    "precompute",
    "sort",
    "binary search",
    "dp",
    "dfs",
    "bfs",
    "segment tree",
    "fenwick",
    "iterate",
    "enumerate",
    "greedy",
    "complexity",
)

TITLE_NOISE = (
    "author:",
    "idea:",
    "preparation:",
    "solution:",
    "editorial:",
    "feedback",
    "good problem",
    "okay problem",
    "bad problem",
    "did not attempt",
    "rate the problem",
)

COMMON_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"Separately solve for cases when David is on left side of both the teachers, in between the teachers and right side of both the teachers\.?",
            re.IGNORECASE,
        ),
        "按 David 在两名老师左侧、两者之间、右侧三种位置讨论。",
    ),
    (
        re.compile(
            r"We need the nearest teacher on the left side and right side, and then B1 solution works\.?",
            re.IGNORECASE,
        ),
        "每次只需要找到询问位置左右最近的老师，然后套 B1 的三种情况。",
    ),
    (
        re.compile(
            r"To find the nearest teachers, you can either use binary search or use lower_bound stl function\.?",
            re.IGNORECASE,
        ),
        "把老师位置排序，用二分或 lower_bound 找左右最近老师。",
    ),
    (
        re.compile(
            r"Help\s+\w+\s+find\s+a\s+string\s+of\s+length\s+\(n\).*?which\s+minimizes\s+the\s+amount\s+of\s+palindrome.*",
            re.IGNORECASE,
        ),
        "构造长度为 n、只含 a/e/i/o/u 的字符串，使回文子序列数量最少。",
    ),
    (
        re.compile(
            r"Narek aims to maximize the value of \(score_n - score_c\).*",
            re.IGNORECASE,
        ),
        "从给定字符串中选若干个按原顺序拼接，最大化 Narek 完整匹配 “narek” 的得分减去未利用目标字母的惩罚。",
    ),
    (
        re.compile(
            r"You have to find the minimum possible value of \(n\) for which such a packing exists\.?",
            re.IGNORECASE,
        ),
        "给定 T/H/U 三种拼块数量，求能把它们全部放进 n×3 网格的最小 n。",
    ),
    (
        re.compile(
            r"You have to help Kevin to find his maximum possible rating after the recalculation.*",
            re.IGNORECASE,
        ),
        "选择一个区间跳过其中比赛，按 rating 规则重算后最大化 Kevin 的最终 rating。",
    ),
    (
        re.compile(
            r"Since constructing a perfect binary tree can be time-consuming.*minimum \(d\).*",
            re.IGNORECASE,
        ),
        "给定一棵树，求最小深度 d，使得某棵深度为 d 的满二叉树经过压缩后能与它同构。",
    ),
    (
        re.compile(
            r"Does there exist an \(n \\times m\) grid of nonnegative integers such that no greedy path achieves the maximum value.*",
            re.IGNORECASE,
        ),
        "判断是否存在 n×m 非负网格，使所有贪心路径都拿不到向右/向下路径的最大路径和。",
    ),
    (
        re.compile(
            r"For each \(i\) from \(1\) to \(n\), determine the number of exploration schemes.*",
            re.IGNORECASE,
        ),
        "对每个 i，计数恰好探索 i 天且最后回到 1 号点的探索方案数。",
    ),
    (
        re.compile(
            r"Given \(p\) and \(q\), determine whether there exist positive integers \(n\) and \(m\).*",
            re.IGNORECASE,
        ),
        "给定直线段数 p 和 L 形块数 q，判断能否拼成某个 n×m 网格，并输出一组可行尺寸。",
    ),
    (
        re.compile(
            r"For example, placing the drain.*What is the maximum amount of water you can get.*",
            re.IGNORECASE,
        ),
        "在地形网格中最多放两个排水口，求能排走的水格子最大数量，重复覆盖只算一次。",
    ),
    (
        re.compile(
            r"The teachers have not yet decided where they will gather the students.*",
            re.IGNORECASE,
        ),
        "对每台咖啡机，求若以它为集合点时最多能聚集多少学生。",
    ),
    (
        re.compile(
            r"So the task is to determine the minimum number of colors required and assign a color.*",
            re.IGNORECASE,
        ),
        "给若干时间线段染色，要求任意被覆盖时刻都有一种颜色只出现一次；求最少颜色并构造染色。",
    ),
    (
        re.compile(
            r"To escape his castle, you have to deduce his function using at most.*",
            re.IGNORECASE,
        ),
        "交互地询问一个 min-max 表达式函数，在限制次数内还原函数并回答后续求值。",
    ),
    (
        re.compile(
            r"On a recent birthday.*asked you to construct an array of positive numbers.*",
            re.IGNORECASE,
        ),
        "构造长度为 n、异或和为 x 的正整数数组，并在所有可行数组中最小化元素和。",
    ),
    (
        re.compile(
            r"Your task is to find how many moves it will take for the teachers to catch David if they all act optimally\.?",
            re.IGNORECASE,
        ),
        "求双方都最优行动时，老师抓住 David 需要多少步。",
    ),
    (
        re.compile(
            r"Ecrade wants to know the minimum number of rounds required for all elements in \(a\) to become equal to \(0\) after exactly \(k\) changes to \(a\)\.?",
            re.IGNORECASE,
        ),
        "允许先对 a 做恰好 k 次减一修改，求经过多少轮抵消并循环移动后 a 全部变为 0。",
    ),
    (
        re.compile(
            r"Therefore, you want to find the number of different common trees.*",
            re.IGNORECASE,
        ),
        "给定两段 DFS 序，求同时能产生这两段序列的不同有根树数量。",
    ),
    (
        re.compile(
            r"Find the minimum possible total cost of the tree after assigning the weights of all vertices with zero initial weight\.?",
            re.IGNORECASE,
        ),
        "把所有初始权值为 0 的点赋为 -1 或 +1，求树上所有子树权值和绝对值之和的最小值。",
    ),
    (
        re.compile(
            r"For each of these \(q\) pairs, you need to find the shortest distance between vertices \(a_i\) and \(b_i\) in this graph\.?",
            re.IGNORECASE,
        ),
        "对每个询问，求图中 a_i 到 b_i 的最短距离。",
    ),
    (
        re.compile(
            r"(?:Solution\s+)?We can use binary search on the answer.*minimum number of changes needed to make.*zero within.*rounds.*",
            re.IGNORECASE,
        ),
        "二分答案 x，并计算要在 x 轮内把 a 清零至少需要多少次预先减一。",
    ),
    (
        re.compile(
            r"Instead, we can cyclically shift.*c_\{n-1\}.*",
            re.IGNORECASE,
        ),
        "把 a、b 同时循环平移到 c_{n-1} 为全局最小值的位置，跨界贡献就不会回到 a_0，于是问题变成线性链。",
    ),
    (
        re.compile(
            r"For the adjusted.*we can greedily process.*",
            re.IGNORECASE,
        ),
        "平移后从右往左贪心：若后面 x 个位置的最小 c_j 大于 c_i，就必须在 a_{i+1} 补足这个差值。",
    ),
    (
        re.compile(
            r"(?:Solution\s+)?Consider\s+\\?mathcal\{O\}\(n\^2\).*dp.*subtree.*",
            re.IGNORECASE,
        ),
        "先做 O(n^2) 树背包：dp[v][子树内 +1 个数] 记录最小代价。",
    ),
    (
        re.compile(
            r"The dp is convex because we are adding only two convex functions.*",
            re.IGNORECASE,
        ),
        "DP 序列保持凸性，因为合并时本质上是在合并两个凸函数。",
    ),
    (
        re.compile(
            r"Then, using small to large, you can achieve.*",
            re.IGNORECASE,
        ),
        "利用凸性只维护差分，再启发式合并可做到 O(n log^2 n)。",
    ),
    (
        re.compile(
            r"Theorem\s+1:\s+Each maximal entangled set and the points in its subtree must form an interval in both DFS sequences\.?",
            re.IGNORECASE,
        ),
        "定理 1：每个极大纠缠集合及其子树点集，在两段 DFS 序中都必须是连续区间。",
    ),
    (
        re.compile(
            r"Theorem\s+2:\s+Among the maximal entangled sets of a leaf node.*",
            re.IGNORECASE,
        ),
        "定理 2：叶子相关的单点极大纠缠集合必须在两段 DFS 序中都是最后出现的集合。",
    ),
    (
        re.compile(
            r"Theorem\s+3:\s+A maximal entanglement set must be connected under the same node in any valid tree\.?",
            re.IGNORECASE,
        ),
        "定理 3：任意合法树中，同一个极大纠缠集合必须挂在同一个父节点下。",
    ),
    (
        re.compile(
            r"By Lucas's theorem the contribution is odd iff.*",
            re.IGNORECASE,
        ),
        "由 Lucas 定理，贡献为奇数当且仅当 n 的每个置位都被唯一一个 cnt_i 接走，也就是二进制加法无进位。",
    ),
    (
        re.compile(
            r"This means that 2\s*cnt_i > n, so i will always be the median\.?",
            re.IGNORECASE,
        ),
        "如果某个值出现次数超过一半，它必然就是中位数。",
    ),
    (
        re.compile(
            r"We can partition all set bits of n into p non-empty subsequences.*",
            re.IGNORECASE,
        ),
        "把 n 的所有置位划分给 p 个非空组，再选择哪些数实际出现。",
    ),
    (
        re.compile(
            r"Let's first simplify the scoring function\.?",
            re.IGNORECASE,
        ),
        "先把得分式化简：完整匹配一个 “narek” 给正分，未完成链上的目标字母会变成惩罚。",
    ),
    (
        re.compile(
            r"Now, dp\[i\]\[j\].*",
            re.IGNORECASE,
        ),
        "设 dp[i][j] 为处理前 i 个字符串后，当前已匹配 “narek” 前 j 个字符时的最大净得分。",
    ),
    (
        re.compile(
            r"Lets fix the count of aeiou.*",
            re.IGNORECASE,
        ),
        "先固定五个元音各出现多少次，问题变成让单字符回文子序列总数最小。",
    ),
    (
        re.compile(
            r"No of palindromes that consist of only a is.*",
            re.IGNORECASE,
        ),
        "只由某个元音构成的非空回文子序列有 2^{C_x}-1 个，五个元音分别贡献下界。",
    ),
    (
        re.compile(
            r"So lowerbound on no of palindrome.*",
            re.IGNORECASE,
        ),
        "因此总下界是五个 2^{C_x}-1 之和；把相同元音分成连续块即可达到这个下界。",
    ),
    (
        re.compile(
            r"We can also use a monotonic stack to maintain the whole process\.?",
            re.IGNORECASE,
        ),
        "也可以用单调栈维护右侧 x 个位置的最小值变化。",
    ),
    (
        re.compile(
            r"You can maintain two sets for each vertex.*",
            re.IGNORECASE,
        ),
        "每个点维护差分两侧的集合，配合启发式合并得到 O(n log^2 n)。",
    ),
    (
        re.compile(
            r"Therefore, we can propose a greedy algorithm: we iterate values v from small to large.*",
            re.IGNORECASE,
        ),
        "按值从小到大贪心匹配：左侧未匹配的 v 尽量接到右侧最近的 v+1，右侧同理。",
    ),
    (
        re.compile(
            r"We can prove that this is correct: Consider an element with a_i=1.*",
            re.IGNORECASE,
        ),
        "正确性来自交换论证：若没有接最近的相邻值，可以把匹配替换到更近的位置且不变差。",
    ),
    (
        re.compile(
            r"Consider using hall theorem.*",
            re.IGNORECASE,
        ),
        "也可以用 Hall 定理看匹配缺口，把问题转成计算 max |S|-|N(S)|。",
    ),
    (
        re.compile(
            r"This problem was initially proposed with a Hall-dp solution.*",
            re.IGNORECASE,
        ),
        "原本可做 Hall-DP，但这里的边结构允许更简单的 O(n) 贪心。",
    ),
    (
        re.compile(
            r"Notice that the answer to a query does not exceed 4 by Lagrange's four-square theorem\.?",
            re.IGNORECASE,
        ),
        "由拉格朗日四平方定理，任意询问答案最多为 4。",
    ),
    (
        re.compile(
            r"To check that the answer is 1.*perfect square\.?",
            re.IGNORECASE,
        ),
        "答案为 1 当且仅当 b-a 是完全平方数。",
    ),
    (
        re.compile(
            r"To check that the answer is 2.*",
            re.IGNORECASE,
        ),
        "答案为 2 时，需要判断距离能否拆成两个平方跳，并处理边界可达范围。",
    ),
    (
        re.compile(
            r"To check that the answer is 3.*",
            re.IGNORECASE,
        ),
        "判断答案为 3 时，枚举第一跳的平方距离，再检查剩余部分是否能两步到达。",
    ),
    (
        re.compile(
            r"Calculate the value of the bitwise XOR of the median.*all good sequences.*",
            re.IGNORECASE,
        ),
        "对所有长度为 n、元素在 [0,m) 且出现次数非降的好序列，计算其中位数的按位异或和。",
    ),
    (
        re.compile(
            r"Please calculate the minimum number of subsequences you can partition.*",
            re.IGNORECASE,
        ),
        "把原序列划分成若干子序列，每个子序列相邻值差必须为 1；求最少需要多少个子序列。",
    ),
)

POST_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\ba 字符串 of length \(([^)]+)\)", re.IGNORECASE), r"长度为 \1 的字符串"),
    (re.compile(r"\ba 序列 of \(([^)]+)\)", re.IGNORECASE), r"长度为 \1 的序列"),
    (re.compile(r"\ba 树 with \(([^)]+)\) vertices", re.IGNORECASE), r"一棵有 \1 个点的树"),
    (re.compile(r"数量 different common trees", re.IGNORECASE), "不同公共树的数量"),
    (re.compile(r"the 最小 possible total cost", re.IGNORECASE), "最小可能总代价"),
    (re.compile(r"the shortest distance", re.IGNORECASE), "最短距离"),
    (re.compile(r"the teachers to catch David", re.IGNORECASE), "老师抓住 David"),
    (re.compile(r"if they all act optimally", re.IGNORECASE), "双方都最优行动时"),
    (re.compile(r"from small to large", re.IGNORECASE), "从小到大"),
    (re.compile(r"using small to large", re.IGNORECASE), "使用启发式合并"),
    (re.compile(r"small-to-large", re.IGNORECASE), "启发式合并"),
    (re.compile(r"lower_bound stl function", re.IGNORECASE), "lower_bound"),
    (re.compile(r"^Solution\s+", re.IGNORECASE), ""),
    (re.compile(r"To 求", re.IGNORECASE), "要求"),
    (re.compile(r"求 the ", re.IGNORECASE), "求"),
    (re.compile(r"需要 求", re.IGNORECASE), "需要求"),
    (re.compile(r"对每个 of", re.IGNORECASE), "对每个"),
)

PROBLEM_OVERRIDES: dict[str, dict[str, Any]] = {
    "2005C": {
        "statement_brief": "给定若干字符串，按原顺序选择一部分拼接；完整匹配目标串 “narek” 得分，未完成链上的目标字符会扣分，求最大净得分。",
        "transformed_statement": "把题目先看成：每个字符串都是一个会改变“当前匹配到 narek 第几位”的转移，选择或跳过字符串来最大化总收益。",
        "key_observations": [
            "完整走完一次 narek 才是真正加分，停在半路的目标字符最后都会变成惩罚。",
            "处理一个字符串时，只需要知道进入前已经匹配到 narek 的哪个前缀位置。",
        ],
        "solution_brief": "关键观察：把每个字符串扫描成 5 种入口状态下的转移收益。设 dp[i][j] 表示处理前 i 个字符串、当前已匹配 “narek” 前 j 个字符时的最大净分；每个字符串只做“选/不选”转移即可。",
    },
    "2013A": {
        "statement_brief": "有 n 个水果，每秒最多放入 y 个、最多搅碎 x 个，求全部搅碎的最少秒数。",
        "transformed_statement": "把题目先看成：系统每秒真正能减少的水果数最多是 min(x,y)，因此只要算 n 对这个速度的上取整。",
        "key_observations": [
            "放入速度和搅碎速度同时限制吞吐量，瓶颈就是 min(x,y)。",
            "没有必要模拟杯中库存，最优每秒都按瓶颈速度推进。",
        ],
        "solution_brief": "关键观察：每秒最多完成 min(x,y) 个水果，且这个上界可以一直达到。答案是 ceil(n / min(x,y))。",
        "primary_topic": "基础实现与模拟",
        "extraction_status": "statement_derived",
    },
    "2029C": {
        "statement_brief": "给定 n 场比赛表现值，选择一个非空连续区间跳过；其余比赛按当前 rating 与 a_i 比较执行 +1/0/-1，最大化最终 rating。",
        "transformed_statement": "把题目先看成：跳过区间把整段转移删掉，前缀 rating 要能接上后缀达到目标 rating 所需的最低入口 rating。",
        "key_observations": [
            "二分最终 rating k，前缀正向模拟得到不跳过时的 f_i。",
            "后缀反推 g_i：进入第 i 场前至少要多少 rating，才能在后缀结束后达到 k。",
            "存在可跳过区间 [l,r] 当且仅当某个 f_{l-1} >= g_{r+1}。",
        ],
        "solution_brief": "关键观察：把“删一段后能否达到 k”拆成前缀可达 rating 和后缀最低入口 rating。正向算 f，反向算 g，枚举右端点并维护前缀最大 f 检查 f_{l-1} >= g_{r+1}；也可用三状态 DP 表示跳过前、跳过中、跳过后。",
    },
    "2031E": {
        "statement_brief": "给定以 1 为根的树，求最小深度 d，使一棵深度 d 的满二叉树经过若干次压缩边/删叶操作后能变成这棵树。",
        "transformed_statement": "把题目先看成：反向把目标树嵌回满二叉树，每个子树消耗若干叶子容量，根深度要覆盖所有儿子需求。",
        "key_observations": [
            "若儿子子树最小需求为 d_c，则多个儿子需要 2^d >= sum 2^{d_c} 的叶子容量。",
            "若只有一个儿子，根必须多留一层，所以 d=d_c+1。",
            "对子树做 DP，按儿子需求合并出最小深度。",
        ],
        "solution_brief": "关键观察：不要正向模拟压缩，而是反向嵌入满二叉树。每个儿子子树占用 2^{d_c} 个叶子容量；多儿子时取满足容量和的最小 d，单儿子时深度必须加一。整棵树后序 DP 即可。",
    },
    "2032F": {
        "statement_brief": "把连续花生口袋分成若干盒；每盒内部是取石子游戏，上一盒输的人成为下一盒先手，求 Alice 能赢的划分数。",
        "transformed_statement": "把题目先看成：每个盒子是一局 Nim/反常 Nim，真正关键不是每盒都赢，而是控制哪一盒输赢来影响下一盒先手。",
        "key_observations": [
            "全 1 盒子的胜负只由奇偶决定；存在大于 1 的口袋时，胜者常可以选择战术性输掉。",
            "全局控制权由第一个非平凡盒决定，前面全 1 盒只是在翻转先手。",
            "枚举第一个非平凡盒的位置，并用前缀异或/计数统计可行划分。",
        ],
        "solution_brief": "关键观察：连续盒子不是独立求胜负，因为败者会成为下一盒先手。先跳过前缀全 1 盒，它们只改变先手奇偶；第一个含大堆的非平凡盒决定谁能掌握后续控制权，再用前缀异或统计这些盒子的划分数。",
    },
    "2046F1": {
        "statement_brief": "给定由 Y/D/X/? 组成的模板，判断能否把 ? 替换成三种字母，使字符串可由每次插入各一个 Y、D、X 且相邻不相同得到，并构造方案。",
        "transformed_statement": "把题目先看成：每段连续问号独立贡献三种字母数量约束，段与段之间只通过总的 Y/D/X 数量相加耦合。",
        "key_observations": [
            "一段问号能放多少个某字母，只受段长和左右边界是否等于该字母影响。",
            "每段可行的 (x,y) 计数区域是一个被斜线切角的凸多边形。",
            "全局可行域是所有段可行域的闵可夫斯基和，最后再贪心恢复每个问号。",
        ],
        "solution_brief": "关键观察：不要逐字符爆搜。把每段 ? 压成三种字母数量约束：0<=每类数量<=上界且总和等于段长；投影到二维后是凸多边形，多段合并就是可行向量求和。合并后若目标计数可达，再逐段分配并恢复字符串。",
    },
    "2046F2": {
        "statement_brief": "给定由 Y/D/X/? 组成的模板，判断能否把 ? 替换成三种字母，使字符串可由每次插入各一个 Y、D、X 且相邻不相同得到，并构造方案。",
        "transformed_statement": "把题目先看成：每段连续问号独立贡献三种字母数量约束，段与段之间只通过总的 Y/D/X 数量相加耦合。",
        "key_observations": [
            "一段问号能放多少个某字母，只受段长和左右边界是否等于该字母影响。",
            "每段可行的 (x,y) 计数区域是一个被斜线切角的凸多边形。",
            "全局可行域是所有段可行域的闵可夫斯基和，最后再贪心恢复每个问号。",
        ],
        "solution_brief": "关键观察：不要逐字符爆搜。把每段 ? 压成三种字母数量约束：0<=每类数量<=上界且总和等于段长；投影到二维后是凸多边形，多段合并就是可行向量求和。困难版利用合并后顶点数很小的结构维护可行域，再贪心恢复字符。",
    },
    "2056F1": {
        "statement_brief": "对所有长度为 n、元素在 [0,m) 且出现次数非降的好序列，求这些序列中位数的按位异或和。",
        "transformed_statement": "把题目先看成：只关心某个值 x 作为中位数的方案数奇偶；偶数次贡献会在异或里抵消。",
        "key_observations": [
            "一个值出现次数超过一半时，它必然是中位数。",
            "Lucas 定理把组合贡献的奇偶变成：n 的每个二进制置位被唯一一个计数项接走。",
            "简单版按出现的不同值个数 p 和候选中位数 x 汇总即可。",
        ],
        "solution_brief": "关键观察：异或只看贡献奇偶。把“x 是中位数”转成计数分配后，由 Lucas 定理判断哪些组合数为奇数：二进制加法不能进位。于是枚举出现值个数 p 与 x，统计奇数贡献。",
    },
    "2057F": {
        "statement_brief": "初始身高数组满足 a_i*2>=a_{i+1}；给若干披萨数 k，问最多增加身高后仍保持舒适时，最大身高能达到多少。",
        "transformed_statement": "把题目先看成：固定最高点位置 i 和目标高度 X，只需要向左补一个每步约减半的最低需求序列。",
        "key_observations": [
            "目标高度 X 放在 i 后，左侧需求依次是 ceil(X/2), ceil(X/4), ...。",
            "因为高度和 k 都不超过 1e9，向左最多影响约 30 个位置。",
            "预处理每个短窗口达到不同目标的代价，再离线/二分回答询问。",
        ],
        "solution_brief": "关键观察：固定最大值位置 i，不需要看很远的左侧，因为每往左需求至少减半，30 步后就无影响。对每个 i 和窗口长度算补到目标 X 的代价区间，再按 k 查询最大可行 X。",
    },
    "2063F2": {
        "statement_brief": "给定平衡括号串，并按顺序加入 good pair；每次加入后，求与当前 good pair 信息相容的括号结构数量。",
        "transformed_statement": "把题目先看成：good pair 会把括号串分解成若干最小平衡括号子序列，答案是这些块的卡特兰因子乘积。",
        "key_observations": [
            "新增 good pair 只会改变它所在的最小平衡括号子序列，外层和内层其它块都不变。",
            "被影响的块最多分成 inside、outside、pair 三类新块。",
            "动态维护这些块的森林结构和对应卡特兰乘积即可。",
        ],
        "solution_brief": "关键观察：困难版不能枚举所有 MBS。加入一个 good pair 时，只有包含这对括号的最小块会被拆开，其它块的计数因子不变；因此维护块森林，每次局部删除旧卡特兰因子、加入分裂后的新因子。",
    },
    "2089C1": {
        "statement_brief": "有若干锁、对应真钥匙和若干假钥匙；玩家按固定顺序轮流尝试钥匙锁组合，成功会开锁并计分。简单版没有假钥匙，要求在所有人按当前最大成功概率行动时计算结果概率。",
        "transformed_statement": "本地题解正文为空，本条只从题面整理：这是一个带信息更新的钥匙试锁随机过程，目标是计算理性选择规则下的概率。",
        "key_observations": [],
        "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
        "extraction_status": "missing_editorial",
    },
    "2089C2": {
        "statement_brief": "有真钥匙和假钥匙、若干锁；玩家轮流尝试钥匙锁组合，要求在各自回合最大化当前成功概率，求过程概率。",
        "transformed_statement": "把题目先看成：每次失败后，剩余信息只影响“同钥匙换锁”和“同锁换钥匙”两类状态的后验概率。",
        "key_observations": [
            "玩家只最大化自己当前回合，因此最优纯策略之间等概率选择。",
            "一次失败后，用贝叶斯/全概率更新同钥匙、同锁两类尝试的成功概率。",
            "困难版把三类转移压成 O(n) 可维护的公共概率。",
        ],
        "solution_brief": "关键观察：不要展开大段条件概率公式。失败事件发生后，“继续拿同一把钥匙试别的锁”和“拿别的钥匙试同一把锁”的后验成功率可以化简成对称表达式；于是 DP 只维护剩余规模和少数公共概率。",
    },
    "2097E": {
        "statement_brief": "给定雪堆高度数组，每分钟选择一个连续段并按该段当前最大值清理，求把所有高度变为 0 的最少时间。",
        "transformed_statement": "把题目先看成：操作段可以重排，使每次段内被指定的最大值按非增顺序出现。",
        "key_observations": [
            "若相邻两次操作的 assigned maximum 逆序，可以交换它们且不变差。",
            "因此存在一个最大值非增的最优操作序列，贪心过程只需要跑一遍。",
            "用集合/线段树维护会在当前高度处理时重新进入考虑的区间。",
        ],
        "solution_brief": "关键观察：先证明操作可以交换到 assigned maximum 非增。这样处理到某个高度时，之前被覆盖但未来仍相关的段会自然回到候选集合；按这个顺序贪心并用数据结构维护区间即可。",
    },
    "2156A": {
        "statement_brief": "每次把一块披萨切成三块，Hao 会吃其中一块；问最优切法下 Hao 总共最多吃几块。",
        "transformed_statement": "把题目先看成：每次都切成 (1,1,m-2)，Hao 每轮稳定拿到 1 块，直到剩余不够继续。",
        "key_observations": [
            "最优切法让两块尽量小，即取 (1,1,m-2)。",
            "每进行一轮，可继续切的规模减少 2。",
            "答案统一为 floor((n-1)/2)。",
        ],
        "solution_brief": "关键观察：两块切成 1 和 1 时最有利，剩余大块继续递归。于是序列是 n -> n-2 -> n-4 ...，Hao 每轮吃 1 块，答案为 floor((n-1)/2)。",
        "primary_topic": "基础实现与模拟",
    },
    "2194B": {
        "statement_brief": "n 个银行账户，每次从一个账户扣 x、另一个账户到账 y(y<=x)，问最后某个账户最多能有多少钱。",
        "transformed_statement": "把题目先看成：选择目标账户 i 后，其它账户能贡献的有效转账次数固定为 sum_{j!=i} floor(a_j/x)。",
        "key_observations": [
            "中转不会增加有效转账次数，因为 y<=x，收款账户的 floor(a/x) 增加至多抵消一次。",
            "目标 i 最多接收 S_all - floor(a_i/x) 次转账。",
            "枚举目标账户取 max(a_i + y*(S_all-floor(a_i/x)))。",
        ],
        "solution_brief": "关键观察：不要考虑复杂转账网络。由于 y<=x，每做一次非目标中转只会消耗一次可转出额度，不能增加最终流向目标的次数。预处理 S_all=sum floor(a_j/x)，枚举目标 i 计算答案。",
    },
    "2196D": {
        "statement_brief": "给定偶长括号串，字符可能是圆括号或方括号；每次可改一个字符，求改成“圆括号子序列合法且方括号子序列合法”的最少修改数。",
        "transformed_statement": "把题目先看成：要为每个括号配对，尽量让配对本身已经同类型且方向正确。",
        "key_observations": [
            "最优配对中，最多只有一个括号对需要 2 次修改；否则可重配不变差。",
            "分别求圆括号和方括号的最长合法括号子序列，保留这些 0 次修改对。",
            "剩余部分只需判断是否需要那一个 2 次修改对。",
        ],
        "solution_brief": "关键观察：O(n^3) 双余额 DP 只是 baseline。真正结构是：最优配对里需要 2 次修改的坏对至多一个，所以先最大化 0 次修改对，也就是分别取圆括号、方括号的最长合法括号子序列；剩余字符再按是否存在一个坏对修正答案。",
    },
    "2201F2": {
        "statement_brief": "初始全白 n×n 矩阵，每次把一个格子染黑；每次询问矩阵是否满足任意两行的黑格集合可按包含关系比较。",
        "transformed_statement": "把题目先看成：每一行是一个集合，矩阵单调等价于所有行集合形成包含关系的全序。",
        "key_observations": [
            "若答案为 YES，按黑格数量排序就等价于按集合包含排序。",
            "把 1 往某个方向“重力推”后，能否保持排序与单调性等价。",
            "困难版维护按大小排序的相邻违规，而不需要存完整 bitset 比较所有行。",
        ],
        "solution_brief": "关键观察：矩阵条件其实是在说任意两行黑格集合不能互相有独有元素，也就是集合链。按黑格数排序后只需检查相邻包含；困难版用“重力推 1”的方向维护行形态和相邻违规数量。",
    },
    "2217H": {
        "statement_brief": "树上有 2n 个人、每个交易编号出现两次；可选择一组不相邻边交换端点上的人，求交换后相邻同编号交易的最大收益。",
        "transformed_statement": "把题目先看成：选边必须是匹配，所以每个点最多移动一步；能成单的交易只可能来自很小邻域。",
        "key_observations": [
            "距离至少 4 的同编号点，即使两端各移动一步也不可能相邻。",
            "根树 DP 中，点 u 最终拿到的徽章只可能来自 u、父亲或某个儿子。",
            "若 u 从某个儿子拿徽章，则这条边已被匹配，那个儿子子树的状态会被限制。",
        ],
        "solution_brief": "关键观察：匹配交换把移动范围限制为 1。把树定根后，f[u][x] 表示 u 最后拿到原来在 x 的徽章时，u 子树内能贡献的最大收益；x 只需枚举 u、父亲、儿子，转移时扣掉被强制交换儿子的独立最优值。",
    },
    "2223E": {
        "statement_brief": "给定两个排列 a,b 和序列 p。区间 I 每次跳到 a、b 在 I 内最大值位置形成的新开区间，询问跳 k 次过程中拼出的 0/1 串最长连续 1，并支持修改 p。",
        "transformed_statement": "把题目先看成：next(l,r) 只由两个排列在区间内的最大值位置决定；固定左端点扫描时，这些 next 关系会形成链/树结构。",
        "key_observations": [
            "固定 l 从右往左扫，维护 φ(l,r)=两个最大值位置组成的新区间。",
            "φ 的相等关系满足单调传播性质，因此所有区间可压成一棵树上的跳转。",
            "修改 p 后，询问变成树上跳 k 次并维护路径/区间里的最长 1 段。",
        ],
        "solution_brief": "关键观察：不要直接模拟区间迭代。把 next(l,r) 的端点对 φ 抽出来，利用它随 l,r 的单调结构把所有状态压到链/树；之后查询就是从一个状态向上跳 k 次，并在经过的 p 片段中维护最长连续 1。",
    },
    "2229G": {
        "statement_brief": "在一条道路上从 x 出发走 k 天，每到房子获得 satisfaction，可停留或移动，求最大总 satisfaction。",
        "transformed_statement": "把题目先看成：长期停留只值得停在从 x 出发路径上的前缀最大房子，换方向也必须围绕这些前缀最大点考虑。",
        "key_observations": [
            "若某房子不是从 x 走来的前缀最大，停留多天不如回到之前更高的前缀最大。",
            "若要换方向，应穿过 x 到另一侧再考虑换，否则仍会被前缀最大停留替代。",
            "维护最早到达各候选点的收益，再用凸包/LCT 等结构处理固定到达时间的最优停留。",
        ],
        "solution_brief": "关键观察：长时间停留的候选点很少，只可能是 x 左右路径上的前缀最大。任何非前缀最大停留都可替换成之前更高点；换方向也要完整穿过 x。于是问题变成在两侧前缀最大链上做到达时间 + 停留收益优化。",
    },
    "2109F": {
        "statement_brief": "给定黑白网格和格子权值，Mouf 与 Fouad 从不同起点走到同一个出口；路径代价是经过格子最大权值，Mouf 可提高黑格权值，要求不让自己的最优代价变差并尽量提高 Fouad 的最小代价。",
        "transformed_statement": "把题目先看成：二分 Fouad 被迫承担的代价阈值 x，判断能否用高权值黑格形成一条阻断 Fouad 的割链，同时仍给 Mouf 留下一条原代价最优路。",
        "key_observations": [
            "若目标阈值 x 不超过 Mouf 原最优代价，怎么抬黑格都不会让 Mouf 更差。",
            "要让 Fouad 过不去，本质是在网格中构造一圈或一条高权值“笼子”来切断可行区域。",
            "当 x 高于 Mouf 原最优代价时，必须先保留一条 Mouf 的超级路径，再在剩余区域里最大化 Fouad 被困住的程度。",
        ],
        "solution_brief": "关键观察：Fouad 的答案具有单调性，因此可以二分阈值 x。对每个 x，先看是否能在不破坏 Mouf 最优路径代价的前提下构造阻断 Fouad 的高权值割链；低阈值直接可行，高阈值则要围绕 Mouf 的一条保留路径分情况建笼，并用最短路/多源搜索计算代价。",
        "primary_topic": "图论与网络流",
    },
    "2207F": {
        "statement_brief": "有一排花札牌，Iroh 每次给 rank 或 color 提示，Zuko 总会打出最左边被提示高亮的牌；要求所有牌按合法顺序打完，并最小化相邻两次提示发生变化的次数。",
        "transformed_statement": "把题目先看成：把相邻相同提示压成提示串，问题变成在 rank 提示段和 color 提示段之间安排顺序，使每张牌被打出时既合法又尽量少切换提示类型。",
        "key_observations": [
            "相邻重复提示没有意义，可以先压缩成 clue string。",
            "rank 提示可以规整成递增顺序；某个 rank 提示一旦出现，会打出所有仍能被它合法打出的较小 rank。",
            "color 提示与 rank 段的相对位置可以通过交换论证规整，之后只剩少量状态需要动态规划。",
        ],
        "solution_brief": "关键观察：不要逐回合搜索提示。先把提示序列规整：连续相同提示压掉，rank 提示按递增顺序排列，并把能交换的 color 提示推到合适段内。规整后用动态规划枚举当前处理到的 rank 边界，转移代价就是中间必须插入或切换的 color 提示数。",
        "primary_topic": "动态规划与状态设计",
    },
    "2055D": {
        "statement_brief": "数轴上有若干稻草人和一只乌鸦，乌鸦若离左侧最近稻草人小于 k 就会瞬移到它右侧 k；稻草人可移动，求最少时间让乌鸦到达位置 l，输出两倍时间。",
        "transformed_statement": "把题目先看成：稻草人相对顺序不应交叉，目标是最大化乌鸦被连续瞬移推进的总距离；总时间等于第一只稻草人就位时间加剩余路程。",
        "key_observations": [
            "拥有乌鸦的稻草人只需要向右移动，反向移动不会带来更优交接。",
            "稻草人的相对顺序不值得交叉，交接点可按原顺序维护。",
            "若设交接位置为 b_i，总瞬移距离是每段 min(k,b_{i+1}-b_i) 的和，最优位置可逐个贪心推出。",
        ],
        "solution_brief": "关键观察：把过程改写为选择一串交接点 b_i。第一个稻草人先到 0，之后每个稻草人只负责把乌鸦尽量向右交给下一个；根据 b_i 与原位置 a_i、时间 T、前一交接点的关系分三种情况更新。二分或直接维护最优 T，即可得到最小时间。",
        "primary_topic": "构造与贪心",
    },
    "2027E1": {
        "statement_brief": "多堆取石游戏中，一次可从某堆取走 d 个，要求 d 是当前石子数 x 的子掩码且不超过限制 a_i；给定每堆初值，判断先手胜负。",
        "transformed_statement": "把题目先看成：每堆独立求格兰迪数，然后把所有堆格兰迪数异或；真正难点是把每堆状态压到少数二进制代表形态。",
        "key_observations": [
            "x 中对应 a 前导零的置位永远不能被有效使用，可以删掉这些位。",
            "删位后状态等价于 x=2^k-1 的满位状态，只需研究限制值 a'。",
            "格兰迪数落入四类闭式：2^k-2、2^k-1、2^k 和中间区间分别处理。",
        ],
        "solution_brief": "关键观察：不要直接在巨大 x 上做博弈。先按二进制把无用位删掉，得到等价的满位状态；再用题解给出的四类格兰迪闭式求每堆值，最后把所有堆异或，非零则先手胜。",
        "primary_topic": "博弈",
    },
    "2108E": {
        "statement_brief": "给定一棵奇数点树，先删除一个点，再把剩余点两两配成同色点对，最大化所有同色点对距离和。",
        "transformed_statement": "把题目先看成：删掉一个叶子后变成偶数点树；在偶数点树中，要让每条边贡献尽可能多，就需要把删边后两侧的点尽量配到不同组。",
        "key_observations": [
            "偶数点树中，最优配对可让每条边贡献 min(size,n-size)。",
            "按重心分组后，每组大小不超过一半，因此可以把不同组的点贪心配对。",
            "原树点数为奇数时，删掉离重心最近的叶子可以保持所有组大小条件。",
        ],
        "solution_brief": "关键观察：先处理偶数点树的最优配对：以重心为中心把点分组，不同组之间配对即可让每条边达到 min(size,n-size) 的贡献。奇数点树只需删除一个最合适的叶子，题解证明删离重心最近的叶子最优；之后按偶数情形配对。",
        "primary_topic": "树结构",
    },
    "2159D1": {
        "statement_brief": "给定序列 c，把它划分成若干连续段；一段的代价为 ceil(最后一个数 / 段内最小值)，求最小总代价。",
        "transformed_statement": "把题目先看成：每段只关心从右往左看的后缀最小值，非后缀最小的元素不会改变任何最优分段代价。",
        "key_observations": [
            "删掉所有非后缀最小值后，最优总费用不变。",
            "最优分段值有很小上界，可以只维护有限个费用层的转移指针。",
            "左端点移动时，最优断点单调，简单版可用多指针动态规划。",
        ],
        "solution_brief": "关键观察：先把序列压成后缀最小值链，原本复杂的段最小值就只会在这条链上变化。又因为单段代价超过某个常数后可以拆分得更优，最优值有小上界；简单版维护每个可能费用层的最远转移位置做动态规划即可。",
        "primary_topic": "动态规划与状态设计",
    },
    "2159D2": {
        "statement_brief": "给定序列 c，对每个子数组都计算“最小划分总代价”，求所有子数组答案之和。",
        "transformed_statement": "把题目先看成：在简单版后缀最小值压缩的基础上，需要把所有左端点的动态规划转移批量维护，而不是逐个子数组重算。",
        "key_observations": [
            "非后缀最小值仍可丢弃，所有有效转移只发生在单调栈维护的最小值链上。",
            "转移代价可以写成随当前 a_i 变化的线性函数。",
            "困难版用可回滚凸包或线段结构维护这些线性函数，配合单调栈处理区间最小值变化。",
        ],
        "solution_brief": "关键观察：困难版不是换一个新公式，而是把简单版的转移批量化。用单调栈维护当前右端点下各左端点的后缀最小值分段；每段产生一批线性转移函数，用可回滚凸包优化查询，右端点前进时增删函数并累加所有子数组答案。",
        "primary_topic": "动态规划与状态设计",
    },
    "2030G2": {
        "statement_brief": "每个星球有一个可毁灭时间区间，可花一次操作把某个区间端点向外扩一格；一个集合的分数是让集合内所有区间有公共交点所需最少扩张次数，求所有非空集合分数总和。",
        "transformed_statement": "把题目先看成：集合分数只由当前最小右端和最大左端的距离贡献；枚举这对“冲突区间”时，其余区间只负责在左右两侧按数量配平。",
        "key_observations": [
            "若区间已有公共交点，贡献为 0；否则必须弥合最大左端与最小右端之间的距离。",
            "固定一对提供最小右端和最大左端的区间后，左右可选区间数量需要相同。",
            "左右同数量选择的求和可用范德蒙德恒等式化简，困难版再滑动维护组合数贡献。",
        ],
        "solution_brief": "关键观察：不要对每个集合单独扩张。分数可分解为一对最小右端、最大左端的距离贡献；固定这对区间后，左侧和右侧额外选入的区间数必须相等，组合数求和用范德蒙德恒等式合并。困难版按端点排序滑动维护这些贡献。",
        "primary_topic": "组合计数与概率",
    },
    "2196A": {
        "statement_brief": "Alice 和 Bob 轮流把 p 或 q 减一；若某一刻分数 p/q 等于 2/3，则 Bob 赢，否则 Alice 赢，判断双方最优下胜者。",
        "transformed_statement": "把题目先看成：Bob 要维持差值 q-p，直到能把局面推到 p:q=2:3；Alice 则试图让分数越过这个目标或耗尽。",
        "key_observations": [
            "若 p>=q，Alice 总能避免到达 2/3。",
            "Bob 能赢当且仅当 p<q 且 min(p/2,q/3)>=q-p。",
            "第二个条件表示在到达 2:3 之前，Bob 有足够步数抵消 Alice 对差值的破坏。",
        ],
        "solution_brief": "关键观察：胜负不是模拟轮流减数，而是看 Bob 能否一直把差值 q-p 维持到目标比例。检查两个条件：必须 p<q，且 min(p/2,q/3) 至少为 q-p；都满足则 Bob 能逼到 2/3，否则 Alice 避开。",
        "primary_topic": "博弈",
    },
    "2152F": {
        "statement_brief": "给定攻击时间数组，多次询问区间 [l,r] 内最多保留多少个攻击，使任意三个被保留攻击的最大最小时间差都大于 z。",
        "transformed_statement": "把题目先看成：排序后只需约束相隔两个位置的攻击，即 y_{i+2}>y_i+z；贪心保留序列会变成两条 successor 链交替前进。",
        "key_observations": [
            "任意三元组安全等价于所有连续三元组安全，即 y_{i+2}>y_i+z。",
            "贪心可以理解为从 l 和 l+1 开始沿 f(i)=第一个大于 x_i+z 的位置跳。",
            "两条跳链第一次相遇的位置是关键冲突点，可用倍增和最近公共祖先思想回答区间询问。",
        ],
        "solution_brief": "关键观察：安全条件只看排序后间隔为 2 的元素。于是最优选择相当于两条链并行跳：一条从第一个选中点开始，一条从第二个选中点开始，每次跳到第一个超过当前值 z 的位置。预处理 successor 和倍增，查询时找两条链在区间内的冲突/汇合点并计算答案。",
        "primary_topic": "数据结构",
    },
    "2032D": {
        "statement_brief": "交互恢复一棵特殊树：删掉根 0 后剩余部分是若干条路径，且父亲编号随节点编号非降；一次询问可判断两点路径是否经过根。",
        "transformed_statement": "把题目先看成：每条从根伸出的路径是一根“触手”，节点编号实际上按层次顺序增长；要把新节点分配到某根触手上。",
        "key_observations": [
            "先连续询问 (1,j)，可确定根连出的触手数量。",
            "父亲编号非降会让节点呈层次顺序，因此某根触手一旦在探测中失败，之后不会再延长。",
            "按编号顺序维护仍可能延长的触手，就能把询问数压到线性级别。",
        ],
        "solution_brief": "关键观察：特殊编号条件非常强，它让节点按层次顺序出现。先用 (1,j) 找出根的直接路径数量；之后对每个新节点，只在仍活跃的触手末端上测试，若某触手不可能再接新节点就停用。这样避免对所有路径反复二次探测。",
        "primary_topic": "交互",
    },
    "2090B": {
        "statement_brief": "初始空网格，每次可从某行左侧或某列上方推入一个球；给定最终 0/1 网格，判断能否通过若干次推球得到。",
        "transformed_statement": "把题目先看成：正向操作等价于把某行最左边的 0 或某列最上面的 0 变成 1，因此每个最终的 1 至少要能从左侧或上侧一路推到。",
        "key_observations": [
            "若一个格子是 1，则它要么左边所有格子都是 1，要么上方所有格子都是 1。",
            "这个条件必要：从行推入需要左侧无空洞，从列推入需要上方无空洞。",
            "它也充分：按 i+j 从大到小反向删除满足条件的 1，可以删完整个网格。",
        ],
        "solution_brief": "关键观察：最终局面可反过来看。一个 1 若左侧存在 0 且上方也存在 0，就不可能是最后一次推出来的；否则可以把它作为最后加入的球删掉。检查所有 1 是否满足“左侧全 1 或上方全 1”，满足即 YES。",
        "primary_topic": "构造与贪心",
    },
    "2134B": {
        "statement_brief": "给定数组和 k；最多做 k 轮操作，每轮可给每个元素选择加 0 或加 k，要求构造最终数组使整体最大公约数大于 1。",
        "transformed_statement": "把题目先看成：只要让所有数都变成同一个大于 1 的模数的倍数即可；选择模数 k+1 会让“加 k”次数自然受控。",
        "key_observations": [
            "对每个 a_i 加上 (a_i mod (k+1))*k 后，它会被 k+1 整除。",
            "因为 a_i mod (k+1) 介于 0 到 k，所以需要的加 k 次数不超过 k。",
            "所有数最终同为 k+1 的倍数，因此最大公约数至少为 k+1。",
        ],
        "solution_brief": "关键观察：不要试图找公共质因子。直接以 k+1 为目标模数：第 i 个数加 t_i 次 k，其中 t_i=a_i mod (k+1)。则 a_i+t_i k ≡ a_i-a_i ≡ 0 (mod k+1)，且 t_i≤k，构造立即成立。",
        "primary_topic": "数论与同余",
    },
    "2257F2": {
        "statement_brief": "平台组成跳跃轨道；海狸每次最多跳 x 格，落回同一平台会产生罚分。支持平台修改和区间询问最小罚分。",
        "transformed_statement": "把题目先看成：每段平台可压成 x×x 转移矩阵，区间答案是矩阵合并；困难版瓶颈是内存。",
        "key_observations": [
            "F1 的线段树每个节点存 x^2 矩阵，x=10 时内存爆掉。",
            "把平台分块，块内重算整块矩阵，块间线段树只维护块矩阵。",
            "询问只需散处理两端残块，中间整块用线段树合并。",
        ],
        "solution_brief": "关键观察：困难版不是时间先炸，而是矩阵线段树内存太大。分块后，每块保存一个整体转移矩阵；查询区间时两端不完整块逐平台处理，中间完整块走线段树，修改只重算所在块。",
    },
}

PROBLEM_OVERRIDES.update(
    {
        "2013B": {
            "statement_brief": "有 n 个战士，每次选择 i<j 让 j 淘汰 i，同时 a_j 减去 a_i；求最后幸存战士的最大可能 rating。",
            "transformed_statement": "把题目先看成：最后一定让第 n 个战士幸存，前 n-1 个战士的贡献可以通过战斗顺序变成“除一个最大可保留外都扣到最后”。",
            "key_observations": [
                "编号小的战士只能被编号大的战士淘汰，所以最终幸存者最优选最右边。",
                "前 n-1 个数里，最大的那个可以先吸收其它人的扣减，减少它对最后一人的负面影响。",
                "答案等价于 a_n + max(a_1..a_{n-1}) - sum(a_1..a_{n-1})。",
            ],
            "solution_brief": "关键观察：不要枚举淘汰树。由于只能 i<j，最后保留第 n 个最优；在前 n-1 个战士中保留一个最大值作为中间赢家，让其它前缀战士先扣它，最后只把这个合并后的值扣到 a_n。公式为 a_n + max(prefix) - sum(prefix)。",
            "primary_topic": "构造与贪心",
        },
        "2031D": {
            "statement_brief": "给定一排不同高度的树；兔子从第 i 棵树出发，按题目跳跃规则移动，求它能到达的最大树高。",
            "transformed_statement": "把题目先看成：答案从右往左传播，i 能否继承 i+1 的答案，只取决于左侧最高树和右侧最低树的相对大小。",
            "key_observations": [
                "从 i 出发一定能到达左侧前缀中的最高树。",
                "若左侧前缀最大值大于右侧后缀最小值，兔子可以跨到右侧连通块，继承 i+1 的答案。",
                "否则 i 的答案就是当前前缀最大值。",
            ],
            "solution_brief": "关键观察：从右往左维护前缀最大 p_i 和后缀最小 s_i。若 p_i>s_i，位置 i 能接入 i+1 所在的可达区域，答案等于 ans_{i+1}；否则右侧跨不过去，答案为 p_i。",
            "primary_topic": "构造与贪心",
        },
        "2034B": {
            "statement_brief": "给定二进制串 s，每次可选择长度为 k 的一段全改成 1；求最少操作次数，使最终不存在长度为 m 的全 0 连续段。",
            "transformed_statement": "把题目先看成：从左到右数连续 0，一旦凑出 m 个 0，这 m 个里面必须至少被一次操作覆盖。",
            "key_observations": [
                "遇到 m 个连续 0 时，这一段必须被处理，不能留给未来。",
                "把长度 k 的操作放在这 m 个 0 的最后一个位置开始，能覆盖最靠右的一段，对未来最有利。",
                "操作后跳过被覆盖的 k 个位置，继续扫描即可。",
            ],
            "solution_brief": "关键观察：贪心的触发点是“刚出现 m 个连续 0”。此时任何合法方案都要覆盖这段中的某个位置；把操作尽量往右放不会损害过去，只会增加未来覆盖。扫描计数，触发后答案加一并跳过覆盖区间。",
            "primary_topic": "构造与贪心",
        },
        "2040F": {
            "statement_brief": "给 a×b×c 的立方体网格染 k 种颜色，三个方向的循环平移视为同一种，求本质不同染色数。",
            "transformed_statement": "把题目先看成：所有三维平移组成一个群；每个平移会把小立方体分成若干循环，固定染色数就是 k 的循环数次方。",
            "key_observations": [
                "Burnside 思路：答案是所有平移下固定染色数量的平均值。",
                "一个平移在三个维度上的循环长度由 gcd 决定，整体循环长度由 lcm 合并。",
                "枚举三个方向的周期类型，用 phi 统计同类平移个数，再做 DP 合并 lcm。",
            ],
            "solution_brief": "关键观察：不是枚举染色，而是枚举平移。对某个平移，处在同一轨道的小立方体必须同色，因此固定方案数是 k^{轨道数}；三维轨道数由各维循环长度的 lcm/gcd 关系算出。最后对所有平移固定点数取平均。",
            "primary_topic": "组合计数与概率",
        },
        "2055E": {
            "statement_brief": "有 n 堆草和容量上限 b_i；必须让每一堆至少清空一次，清空后该堆最多只能再放 b_i 根草，求最少搬动次数或判无解。",
            "transformed_statement": "把题目先看成：先固定清空顺序，只有最后一堆承担临时缓冲；额外搬到最后一堆的数量由一个前缀最大值决定。",
            "key_observations": [
                "固定清空顺序后，可行性只取决于最后一堆能否最终被清空。",
                "额外必须堆到最后一堆的草量是 max(prefix sum a - previous prefix sum b)。",
                "交换相邻顺序可推出最优排序规则，再枚举最后一堆并用线段树维护表达式。",
            ],
            "solution_brief": "关键观察：先固定清空排列 σ。前面堆满时，多出来的草只能暂放最后一堆，所以代价多出一个前缀最大量；最优顺序可由相邻交换比较得到。枚举最后清空的堆，剩余堆按规则排序，用线段树维护这个前缀最大表达式。",
            "primary_topic": "构造与贪心",
        },
        "2071A": {
            "statement_brief": "三个人无限打乒乓，每场两人打、一人旁观；没人能连续打三场。问第一场旁观者能否也是第 k 场旁观者。",
            "transformed_statement": "把题目先看成：无论每场谁赢，旁观者序列都会按长度 3 的周期循环。",
            "key_observations": [
                "某人连续打两场后下一场必须旁观，胜负不会改变这个约束。",
                "因此第一场旁观者只会出现在第 1、4、7、... 场旁观。",
                "判断 k mod 3 是否等于 1 即可。",
            ],
            "solution_brief": "关键观察：比赛胜负看似有分支，但“不能连续打三场”会强制第三场的参与者。列出前几场后可见旁观者每 3 场循环一次，所以答案是 k%3==1。",
            "primary_topic": "基础实现与模拟",
        },
        "2081G1": {
            "statement_brief": "给定 n，计算 sum_{k=1}^n (k mod phi(k))，最后对 2^32 取模；简单版 n 上限较小。",
            "transformed_statement": "把题目先看成：按 k/phi(k) 的整数部分分组，因为 k mod phi(k)=k-phi(k)*floor(k/phi(k))。",
            "key_observations": [
                "k/phi(k) 只由 k 的不同质因子集合决定。",
                "加入一个很大的新质因子通常不会改变 floor(k/phi(k))；题解给出改变时的质数大小界。",
                "据此只枚举会改变取整值的质因子组合，并用 phi 前缀和汇总贡献。",
            ],
            "solution_brief": "关键观察：直接枚举到 n 不可能。把余数写成 k-phi(k)*g(k)，其中 g(k)=floor(k/phi(k))；g(k) 只有在质因子集合变化到足够“密”时才跳变。简单版利用“乘入大质数不改变 g”的界限枚举关键状态，再用质数 phi 前缀和补贡献。",
            "primary_topic": "数论与同余",
        },
        "2081G2": {
            "statement_brief": "给定 n，计算 sum_{k=1}^n (k mod phi(k))，最后对 2^32 取模；困难版 n 上限更大。",
            "transformed_statement": "把题目先看成：沿用 简单版的 g(k)=floor(k/phi(k)) 跳变状态，但必须更快求大范围 phi 子树和。",
            "key_observations": [
                "答案仍围绕 k-phi(k)*g(k) 展开，关键是高效求满足状态条件的 phi 和。",
                "困难版把枚举状态组织成按最大质因子扩展的 DFS 树。",
                "大块 phi 前缀和用 Min25/杜教筛式卷积分块思想计算，避免展开所有数。",
            ],
            "solution_brief": "关键观察：困难版难点不在公式变了，而在 phi 前缀和规模太大。保留 简单版的跳变状态树，对每个状态求其子树中 phi 的总贡献；这些子树和再用数论分块/筛式前缀和计算，最后只遍历重要节点。",
            "primary_topic": "数论与同余",
        },
        "2097F": {
            "statement_brief": "环形机场网络每天把滞留行李运到前一站、原站或后一站并受容量限制；对每一天求最多仍未归还的行李数。",
            "transformed_statement": "把题目先看成：建分层流后，第 i 天答案是从源点到第 i 层汇点的最大流；但需要同时求所有连续汇点的最大流。",
            "key_observations": [
                "朴素对每个汇点单独跑最大流会过慢。",
                "每层只有 n 个点，最小割可压成当前层点属于 S/T 的 bitmask 状态。",
                "连续天数的割结构可以动态转移，复用上一层计算。",
            ],
            "solution_brief": "关键观察：分层流模型很直接，真正瓶颈是要对 t_1..t_m 都求最大流。转到最小割视角后，令 dp[k][mask] 表示处理到第 k 层且该层 S/T 分布为 mask 的最小割，逐层转移即可同时得到所有天的答案。",
            "primary_topic": "图论与网络流",
        },
        "2115E": {
            "statement_brief": "在 DAG 上从 1 走到 boss 点 p，沿途可用金币买卡；多次询问初始金币 r，求到达 p 时卡牌战力最大和。",
            "transformed_statement": "把题目先看成：路径上有一个最高性价比买卡点；金币足够大时，除了这个点以外只需要考虑有限金额的“余数/特殊购买”。",
            "key_observations": [
                "小 r 可以直接做状态 DP。",
                "大 r 时，最优策略会把绝大多数金币花在路径上性价比最高的点。",
                "其它点的购买量可以压到最高性价比点费用 C 以内，否则可用鸽巢/取模交换改进。",
            ],
            "solution_brief": "关键观察：多询问不能把金币维度开到 r。对每条路径枚举最高性价比点 v；大金币时，除 v 外的特殊购买总费用只需枚举到 O(C)，剩余金币全投给 v。于是小 r 用 DP，大 r 枚举主点和有限余数状态。",
            "primary_topic": "动态规划与状态设计",
        },
        "2118E": {
            "statement_brief": "奇数 n×m 白色网格要按某个顺序全部染色；每染一个格子，会给当前最远的已染格子加罚分，要求每格罚分不超过 3。",
            "transformed_statement": "把题目先看成：先会做较小的 (n-2)×m，再把上下两条长边按交替顺序补上。",
            "key_observations": [
                "n、m 都为奇数保证有中线，可以让新加两边互为最远侧。",
                "先染两条长边的中点，随后沿两侧上下交替扩展。",
                "角落是唯一特殊处，调整横向/纵向扩展顺序即可控制罚分。",
            ],
            "solution_brief": "关键观察：构造是递归扩展，不是全局搜索。假设 n>=m，先解决 (n-2)×m；新增上下两行时先染两条边的中点，再交替向两端染色，使新增罚分主要落到对侧且每格最多增加常数次。角落用扩展顺序处理。",
            "primary_topic": "构造与贪心",
        },
        "2124I": {
            "statement_brief": "定义 f(a) 为所有分段中，使各段最小值序列字典序最大的分段数 k；给定 x_i，判断是否存在排列 a 使每个前缀的 f 值等于 x_i，并构造排列。",
            "transformed_statement": "把题目先看成：x_i 是一棵树的深度序列，父亲是前面最近的 x_j=x_i-1 的位置。",
            "key_observations": [
                "先分析给定排列如何求 f：遇到第一个小于首元素的位置后，最优切点由前缀最大值决定。",
                "反向构造时，x_i 不能一次增加超过 1。",
                "同深度段之间会产生大小约束，把这些约束建成树/偏序后再赋排列值。",
            ],
            "solution_brief": "关键观察：不要直接试排列。把 x 看成深度：对每个 i，找最近的上一层位置 j 作为父亲；若 x_i-x_{i-1}>1 立即无解。题解从 f 的递归分段规则推出父子和兄弟间的大小约束，再按这些约束给节点编号即可构造排列。",
            "primary_topic": "树结构",
        },
        "2127C": {
            "statement_brief": "给两数组 a,b，进行 k 轮：Ali 选两个下标，Bahamin 可任意重排这四个数；最终代价为 sum |a_i-b_i|，双方最优，求最终值。",
            "transformed_statement": "把每个下标看成区间 [min(a_i,b_i), max(a_i,b_i)]；Ali 想选两个区间让 Bahamin 无法增加总代价。",
            "key_observations": [
                "同下标内交换或同时重排下标不影响问题，可假设 a_i<=b_i。",
                "若存在两个区间相交，Ali 每轮选它们即可让总值保持不变。",
                "若所有区间不相交，Bahamin 的最小可增加量由排序后相邻区间的最小间隙决定。",
            ],
            "solution_brief": "关键观察：四个数重排后的最大增量只取决于两个区间是否相交。相交则 Ali 能把答案锁在初始 sum(b_i-a_i)；不相交时，只需按左端点排序找最近两区间，额外代价为 2*gap。",
            "primary_topic": "构造与贪心",
        },
        "2133D": {
            "statement_brief": "n 个怪物上下堆叠，每次攻击任意怪 1 点血；怪死后上方整段掉落，最下面那个按原下方怪物数受到坠落伤害，求全杀最少攻击数。",
            "transformed_statement": "把题目先看成：每个怪物只会选择三种命运之一：直接打死、吃 1 点坠落伤害、或在原栈中吃最大坠落伤害。",
            "key_observations": [
                "一个怪物受到坠落伤害后会成为栈底，不可能再次坠落受伤。",
                "若某怪要吃超过 1 点坠落伤害，下面那个怪必须是直接被打死的。",
                "因此决策只依赖相邻两层，可做一维 DP。",
            ],
            "solution_brief": "关键观察：坠落看似会连锁，但每个怪最多吃一次坠落伤害。对第 i 个怪，最优只需比较两种转移：让它在前一怪死亡后吃 1 点伤害，或先直接打死 i-1 让 i 在原栈中吃 i-1 点伤害。令 dp[i] 为杀死前 i 个的最小攻击数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2135D2": {
            "statement_brief": "交互题：隐藏一个编辑器行宽 W；你可提交若干单词长度组成的文章，系统返回排版所需行数；困难版限制总单词数，要求确定 W。",
            "transformed_statement": "把题目先看成：第一次用很多个 1 把 W 缩到区间 [L,R]，第二次构造一串二元组直接编码 W-L。",
            "key_observations": [
                "询问 10^5 个长度 1 的单词，可得到 ceil(10^5/W)，从而确定 W 所在区间。",
                "这个区间满足 2L>R，所以 (L,x) 这样的二元组不会和下一组串行干扰。",
                "第二次询问的行数能线性反推出 W。",
            ],
            "solution_brief": "关键观察：先用全 1 文章得到 r=ceil(10^5/W)，解出 W∈[L,R]。由于该区间有 2L>R，可以询问 (L,1),(L,2),...,(L,R-L)：每组占一行还是两行只由 L+x<=W 决定，因此返回行数直接给出 W。",
            "primary_topic": "交互",
        },
        "2147E": {
            "statement_brief": "给定数组；每个询问允许做至多 b 次“某个元素加 1”，最大化整个数组按位或中 1 的个数。",
            "transformed_statement": "把题目先看成：要多点亮若干 bit 时，最优会从低到高补齐当前或值中的缺失 bit。",
            "key_observations": [
                "答案最多 31，因为数值范围只涉及 0..30 位。",
                "若要点亮第 p 个缺失 bit，应选择距离拥有该 bit 最近的元素加到对应阈值。",
                "题解用交换论证证明：先点亮更低的缺失 bit 不会比跳去更高 bit 更差。",
            ],
            "solution_brief": "关键观察：对每个可能答案增量，贪心模拟点亮当前按位或中最靠低的缺失 bit。每次找一个元素，把它加到能打开该 bit 的最近值；花费前缀单调，预处理得到达到 0..31 个 1 所需最小操作数，再回答每个 b。",
            "primary_topic": "数据结构",
        },
        "2147I1": {
            "statement_brief": "构造长度 n 的整数序列，只使用至多 m 个不同值，并使相邻跳跃距离严格递增。",
            "transformed_statement": "把题目先看成：先在二维里绕多边形按步长跳，再把这些点投影到数轴，同时保持边长递增。",
            "key_observations": [
                "用 m 个点时，按跳过 k 个点的方式来回走，可以获得约 m log m 次跳跃。",
                "构造相邻点间距为 C+1,C+2,...，保证投影后多数跳跃长度仍随时间变大。",
                "转向处需要证明不用增大 k 也能保持距离递增。",
            ],
            "solution_brief": "关键观察：不要试图随机找 n 个数。先造至多 m 个可重复访问的点，点间距离设计成严格递增的大数列；第 k 轮从左到右、再从右到左每次跳过 k 个点。这样每轮贡献约 m/k 次跳跃，总计约 m log m，足够覆盖 简单版。",
            "primary_topic": "构造与贪心",
        },
        "2150F": {
            "statement_brief": "给定连通无向图；一次操作选择 k，并输出若干条长度 k-1 的简单路径，把每条路径两端加边。要求至多 2 次操作把图补成完全图。",
            "transformed_statement": "把题目先看成：只取一棵生成树。第一次用 k=3 补所有树距 2 的边；第二次用直径 D 控制所有剩余点对的路径长度。",
            "key_observations": [
                "第一次 k=3 后，树上距离 1 和 2 的点对都有边。",
                "第二次取 k=floor(D/2)+1，任意点对都能构造出恰好 k-1 长度的简单路径连接。",
                "距离不够时沿直径两端绕路“浪费步数”。",
            ],
            "solution_brief": "关键观察：原图多余边不用管，取任意生成树即可。先用 k=3 增加所有距离 2 的边；再以树直径为骨架，选择约 D/2+1 的 k。对任意未连点对，若真实距离不足，就往直径端点方向绕出足够长度，输出对应简单路径。",
            "primary_topic": "图论与网络流",
        },
        "2151A": {
            "statement_brief": "黑板上依次写 1；1,2；1,2,3；直到 1..n。给定保证出现的数组 a，求它作为连续子数组出现多少次。",
            "transformed_statement": "把题目先看成：若 a 内部出现下降或不增，它只能跨过某个块边界；否则它就是一段连续递增区间。",
            "key_observations": [
                "若存在 a_i>=a_{i+1}，必然是形如 k,1 的跨块边界，出现位置唯一。",
                "否则 a 是 l,l+1,...,r，可以出现在每个长度至少 r 的块里。",
                "答案分别为 1 或 n-r+1。",
            ],
            "solution_brief": "关键观察：串 b 由递增块 1..t 拼接而成。模式 a 只要发生一次不增，就锁定唯一的块边界，答案为 1；若全程严格递增，则 a=[l..r]，从第 r 块到第 n 块各出现一次，答案 n-r+1。",
            "primary_topic": "字符串",
        },
        "2152B": {
            "statement_brief": "Krug 和 Doran 在 (n+1)×(n+1) 网格追逃；Krug 每回合只能上下左右或停留，Doran 可八方向或停留。双方最优，求 Krug 存活时间或无限。",
            "transformed_statement": "把题目先看成：Krug 只需要沿行或列跑向边界；Doran 的最优追击给出同一个时间上界。",
            "key_observations": [
                "若 Krug 在 Doran 上方，就往 0 行跑；在下方就往 n 行跑，列方向同理。",
                "这个策略给出存活时间下界：Doran 到对应边界所需步数。",
                "Doran 每步同时缩小行差和列差，能达到同样上界。",
            ],
            "solution_brief": "关键观察：二维追逃可以拆成行、列两个一维边界距离。Krug 选择一个能跑向的边界拖时间；Doran 用八方向贪心同时缩小两轴差距。上下界重合，所以答案就是行/列对应边界距离的最大值。",
            "primary_topic": "博弈",
        },
        "2163D1": {
            "statement_brief": "交互题：隐藏一个 0..n-1 的排列，并给 q 个区间；可询问任一区间 MEX，要求找出给定区间中最大的 MEX，简单版询问次数约 n/2。",
            "transformed_statement": "把题目先看成：先删掉被其它区间包含的无用区间，再利用 0 的位置所在半边减少候选。",
            "key_observations": [
                "若区间 A 被区间 B 包含，则 MEX(A)<=MEX(B)，A 不可能成为唯一最优。",
                "清理包含关系后，每个左端点最多保留一个右端点。",
                "询问前半区间判断 0 在哪半边，再丢掉不含 0 的区间，候选数降到约 n/2。",
            ],
            "solution_brief": "关键观察：最大 MEX 的区间必须尽量大且必须含 0。先删掉所有被包含区间；再问 [1,n/2] 判断 0 的半边，只保留可能含 0 的候选区间。剩下区间数不超过 ceil(n/2)，逐个询问取最大即可。",
            "primary_topic": "交互",
        },
        "2163D2": {
            "statement_brief": "交互题：隐藏排列并给 q 个区间；困难版只能约 30 次询问，要找这些区间 MEX 的最大值。",
            "transformed_statement": "把题目先看成：区间 MEX 可由一个前缀 MEX 和一个后缀 MEX 的较小值表示，从而能二分候选区间集合。",
            "key_observations": [
                "对任意 [l,r]，MEX(p[l..r])=min(MEX(p[1..r]), MEX(p[l..n]))。",
                "清掉包含区间后，候选区间按端点有序，选中间区间可以把集合分成左右两半。",
                "用少量前缀/后缀询问判断最优在左边还是右边。",
            ],
            "solution_brief": "关键观察：把区间 MEX 拆成前缀与后缀 MEX 的 min。对清理后的候选区间做二分，每次围绕中间区间询问相关前缀/后缀，判断最大值不可能在哪一侧，从而把候选集合减半，30 次内定位答案。",
            "primary_topic": "交互",
        },
        "2173D": {
            "statement_brief": "从整数 n 开始，做 k 次操作，每次加 2^l；一次操作得分为二进制加法产生的进位数，求总得分最大值。",
            "transformed_statement": "把题目先看成：总进位数等于 popcount(n)+k-popcount(n')，所以要让最终 n' 的 1 尽量少。",
            "key_observations": [
                "若 k 足够大，可以每次加到最低能产生进位的位置，最终到达 2 的幂。",
                "一般情况下，只需在二进制位上决定哪些位被加过。",
                "DP 状态记录处理到第几位、用了几次操作、是否有进位。",
            ],
            "solution_brief": "关键观察：不要逐次贪心模拟所有 k。把 k 次加法合并看最终二进制：总进位 = 初始 1 的个数 + 操作数 - 最终 1 的个数。因此问题变成最小化最终 popcount，用按位 DP 处理选择当前位是否加一次以及进位传递。",
            "primary_topic": "动态规划与状态设计",
        },
        "2178A": {
            "statement_brief": "给定只含 Y/N 的字符串，每次把相邻两字符按 OR 合并成一个字符，但禁止合并两个 Y；问能否最终缩成一个字符。",
            "transformed_statement": "把题目先看成：操作不会改变字符串中 Y 的数量。",
            "key_observations": [
                "Y+N 会变成 Y，N+N 会变成 N，因此 Y 的数量保持不变。",
                "若初始至少两个 Y，最终单字符不可能仍含两个 Y。",
                "若初始至多一个 Y，任意合并都不会遇到 Y+Y。",
            ],
            "solution_brief": "关键观察：Y 的个数是不变量。最终长度为 1，所以初始 Y 数必须不超过 1；反过来若不超过 1，就永远不会被迫合并两个 Y，答案为 Yes。",
            "primary_topic": "字符串",
        },
        "2178D": {
            "statement_brief": "n 个精灵初始生命等于攻击力且攻击力互不相同；每个精灵最多攻击一次，攻击双方互相扣对方攻击力。构造攻击序列，使最后恰好 m 个精灵存活。",
            "transformed_statement": "把题目先看成：每个幸存精灵必须杀死一个更小的目标，所以幸存者数量最多为 floor(n/2)。",
            "key_observations": [
                "每次攻击至少死一个精灵，且较小攻击力的一方一定会死。",
                "幸存精灵必须已经攻击过，并对应一个被它杀死的目标；目标不能被多个幸存者共享。",
                "当 0<m<=n/2 时，取最大 m 个做幸存者、次大 m 个做目标，其余用链式攻击自杀。",
            ],
            "solution_brief": "关键观察：先判 2m<=n。若 m>0，把精灵按攻击力排序：最大 m 个作为最终幸存者，次大 m 个作为它们的靶子，剩余小精灵按从小到大攻击右侧更大的精灵让自己死亡；最后幸存者分别攻击目标。m=0 需额外判断除最大者外攻击力总和能否杀死最大者。",
            "primary_topic": "构造与贪心",
        },
        "2178I": {
            "statement_brief": "平面上有 n 个整点城市；若两城距离为 sqrt(k) 则连边。统计满足题目烟花发射条件的方案数并取模。",
            "transformed_statement": "把题目先看成：先按距离 sqrt(k) 建图；不断把偶数 k 旋转缩放，直到图分解成二分图结构。",
            "key_observations": [
                "距离条件按奇偶变换后会把图拆成独立连通块。",
                "最终每个连通块是二分图，可选择较小侧枚举子集。",
                "对另一侧用子集 DP 统计每个非发射点邻接 0/1 个发射点的贡献。",
            ],
            "solution_brief": "关键观察：几何距离只是建图入口。对偶 k 反复做坐标旋转缩放归约，得到若干二分图块；每块取较小侧枚举发射集合，另一侧的合法选择数通过邻接掩码的子集 DP 累计，最后各连通块相乘。",
            "primary_topic": "图论与网络流",
        },
        "2183I1": {
            "statement_brief": "给二进制串，第 x 次操作可选择 l，同时翻转 s_l 和 s_{l+x}；要求输出所有操作，使最终 1 的数量不超过 15。",
            "transformed_statement": "把题目先看成：按操作长度的奇偶把字符串两半分别消去，难点是把少数无法配对的 1 递归压小。",
            "key_observations": [
                "偶数 n 可先忽略最后一位，只处理奇数长度核心。",
                "把串分成左右两部分，用奇数长度消一边、偶数长度消另一边。",
                "每次配对失败时，剩余问题规模至少缩到约三分之一，因此残留 1 数有对数上界。",
            ],
            "solution_brief": "关键观察：不要为每个 1 单独找操作。把问题递归地看成区间消除：两端相同就直接翻转配掉，两端不同就借助区间外的一个 1 转移位置；真正失败的情况会让区间长度至少缩成三分之一，所以 简单版最终残留不超过 15。",
            "primary_topic": "构造与贪心",
        },
        "2201A1": {
            "statement_brief": "给定一个可能由“在某个元素后插入 x_i+1”生成的序列 a，求最短初始序列长度。",
            "transformed_statement": "把题目先看成：初始序列的每个元素对应最终序列中的一个连续段，判断当前 a_i 能否并入上一段。",
            "key_observations": [
                "若上一段首值为 x、当前尾值为 y，则可并入条件是 x+1<=a_i<=y+1。",
                "不满足时，a_i 必须开启一个新的初始元素段。",
                "也可从右到左用栈反向消去 a_i+1。",
            ],
            "solution_brief": "关键观察：每个初始数生成最终的一段连续子序列。左到右维护当前段的首值 x 和尾值 y；若 a_i 能由段内某个值加一得到，即 x+1<=a_i<=y+1，就并入，否则新开一段。段数就是答案。",
            "primary_topic": "数据结构",
        },
        "2201A2": {
            "statement_brief": "对数组 a 的每个子数组 c，定义 f(c) 为能生成 c 的最短初始序列长度；求所有子数组 f(c) 之和。",
            "transformed_statement": "把题目先看成：对每个右端点维护所有后缀的最短构造栈，并累计栈中元素对各前缀的贡献。",
            "key_observations": [
                "简单版的右到左栈算法能同时维护某个后缀的最短初始序列。",
                "栈中的每个元素出现时刻决定它贡献给多少个前缀。",
                "记录入栈位置后，可 O(1) 得到当前后缀的所有前缀贡献和。",
            ],
            "solution_brief": "关键观察：困难版不是重做所有子数组，而是让栈同时代表当前后缀的所有前缀。右到左扫描时，消去栈顶的 a_i+1 再压入 a_i；每个栈元素记录它从哪个左端点开始存在，由此累计所有前缀 f 值，总体 O(n)。",
            "primary_topic": "数据结构",
        },
        "2207E1": {
            "statement_brief": "给定序列 a_i，要求构造非负数组 b，使得每个前缀 b_1..b_i 的 (n-i+1)-mex 等于 a_i，或判断无解。",
            "transformed_statement": "把题目先看成：倒着维护还没出现的数集合 S；a_i 描述的是 S 中第 n-i+1 小的缺失位置。",
            "key_observations": [
                "必要条件是 n-i<=a_i<=n，并且 a_i 随 i 非增。",
                "从后往前看，每一步相当于往缺失集合里放回一个数。",
                "若 a_i 不变，就选择当前可放回的最大安全数；若下降，就必须放回触发下降的边界值。",
            ],
            "solution_brief": "关键观察：正向 MEX 不好构造，反向缺失集合更清楚。先检查 a_i 的范围和单调性；然后从 i=n 往 1 还原 b_i，维护哪些数仍缺失，按 a_i 是否变化决定放回哪个数。所有条件满足即可输出构造。",
            "primary_topic": "构造与贪心",
        },
        "2207E2": {
            "statement_brief": "Counting 版：给定 a_i，统计有多少数组 b 满足每个前缀的 (n-i+1)-mex 都等于 a_i。",
            "transformed_statement": "把题目先看成：和构造版一样倒着维护缺失集合 S，但现在要统计每个“平稳步”有多少可选数。",
            "key_observations": [
                "同样先判 n-i<=a_i<=n 且 a_i 非增。",
                "a_i 下降的位置强制删除/放回特定边界，选择数很少。",
                "a_i 不变的位置是 good step，可从当前缺失集合中的安全元素里选，贡献相乘。",
            ],
            "solution_brief": "关键观察：倒着看缺失集合。每次 a_i 变化时，集合结构被强制推进；a_i 不变时，b_i 可以选择一个不会改变目标 MEX 的安全数。维护可选安全数数量，遇到 good step 乘上当前选择数即可。",
            "primary_topic": "组合计数与概率",
        },
        "2207G": {
            "statement_brief": "网格中有必须满足的 needy 格和 special 格，要求选择一批格子染黑，使收益达到阈值并满足操作可行性。",
            "transformed_statement": "把题目先看成：可染黑集合在边相邻图中必须是森林；若有环，就删掉某些非 special 格来破环。",
            "key_observations": [
                "当所有格子价值相同，可行黑格集合等价于没有环的格子邻接森林。",
                "三种条纹平移的平均覆盖保证能选到足够多的普通格。",
                "special 不邻接 needy，因此每个环上总能找到可删的非 special 格破环。",
            ],
            "solution_brief": "关键观察：操作可行性本质是森林条件。先用三种条纹方案保证覆盖比例，再把产生的环逐个打断；由于 special 与 needy 不相邻，破环时总能删普通格而不损坏必须保留的结构，最终仍能达到所需收益。",
            "primary_topic": "图论与网络流",
        },
        "2211B": {
            "statement_brief": "在长度 x+y、含 x 个 1 和 y 个 -1 的数组中，最小化把数组切成若干等和子数组的方案数 f(a)，并构造达到最小值的数组。",
            "transformed_statement": "把题目先看成：前缀和每步只变 ±1，所以从 0 到 x-y 会经过所有中间高度。",
            "key_observations": [
                "若 d 整除 |x-y|，前缀和必然依次经过 d,2d,...，因此至少有一种等和为 d 的切法。",
                "所以 f(a) 至少是 |x-y| 的约数个数。",
                "把所有 1 放前面、所有 -1 放后面可以达到这个下界；x=y 另作零和构造。",
            ],
            "solution_brief": "关键观察：切分等和就是看前缀和命中等差高度。因为前缀和每步只走 ±1，任何 |x-y| 的约数 d 都强制产生一类切分，这是下界；单调构造 [1..1,-1..-1] 让每个 d 只产生一次，从而达到最小值。",
            "primary_topic": "数论与同余",
        },
        "2219C": {
            "statement_brief": "树上已有红/黑点，通过随机/选择操作把黑点染红；求最优策略下的最小期望操作数。",
            "transformed_statement": "把题目先看成：红点把树切成若干黑色连通块，每个块只需要考虑与其相邻红点作为边界。",
            "key_observations": [
                "不同黑色连通块可独立处理，再由相邻红点连接。",
                "对黑块定根后，dp[u][0/1] 表示 u 在父亲前/后被染红时的最小期望。",
                "多个儿子的处理顺序影响期望，按 dp[child][1]-dp[child][0] 排序最优。",
            ],
            "solution_brief": "关键观察：先用已有红点把问题切块。每个黑色连通块做树 DP，状态区分父节点是否已经变红；染当前点前需要等待某些儿子事件，儿子顺序可用交换论证按收益差排序。把所有块贡献相加即为答案。",
            "primary_topic": "树结构",
        },
        "2226G": {
            "statement_brief": "给数组 a 和所有 1..m 的排列 p，拼成 b=a+p；令 f(i) 为产生恰好 i 个偶长回文子数组的排列数，求 sum f(i)^{i+1}。",
            "transformed_statement": "把题目先看成：a 内部偶回文数量固定，新增偶回文只能跨越 a 与排列 p 的边界。",
            "key_observations": [
                "跨边界偶回文必须形如 S + R + rev(S)，其中 R 是 a 的偶回文后缀。",
                "因为 p 是排列，S 内字符必须两两不同，rev(S) 必须是 p 的前缀。",
                "把所有 rev(S) 插入 trie，DFS 枚举排列前缀并累计每条路径创造的跨界回文数。",
            ],
            "solution_brief": "关键观察：排列内部没有重复元素，所以新增偶回文只可能跨 a|p 边界。枚举 a 的偶回文后缀 R，并向左扩展无重复段 S，条件就是 p 前缀等于 rev(S)。把这些模式放入 trie，遍历 trie 统计每种跨界回文数量对应的排列数，再代入公式。",
            "primary_topic": "字符串",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2023F": {
            "statement_brief": "道路被分成 n 段，每段高度可正可负；卡车初始空载、可搬沙并在相邻段间移动。对多个区间询问，求只使用该区间内沙土把所有高度归零的最短移动时间，或判无解。",
            "transformed_statement": "把题目先看成：区间前缀和决定每条相邻边至少要被走几次；前缀和为负的位置边至少走 3 次，否则通常只需 1 次。",
            "key_observations": [
                "单个区间若总和为负则无解，否则可以从左到右修平。",
                "在固定从左到右的模型中，前缀和 p_i<0 的边必须额外返回补沙，所以走 3 次；p_i>=0 的边走 1 次。",
                "多询问时要支持区间前缀和整体平移后的负位置统计，用线段树维护替换/拼接状态。",
            ],
            "solution_brief": "关键观察：卡车移动次数不是模拟装卸，而是由区间前缀和符号决定。前缀和为负说明左侧缺沙，卡车必须跨边返回再回来，边贡献 3；否则贡献 1。去掉固定起终点后再处理两端可节省的部分，多询问用线段树维护区间合并状态。",
            "primary_topic": "数据结构",
        },
        "2032A": {
            "statement_brief": "有 n 盏灯和 2n 个开关，每盏灯连两个未知开关；给出所有开关开关状态，求可能亮灯数的最小值和最大值。",
            "transformed_statement": "把题目先看成：每盏灯亮当且仅当它连接的一对开关状态一开一关，所以只是在配对 0 和 1。",
            "key_observations": [
                "最大亮灯数是尽量把 0 和 1 配对，即 min(cnt0,cnt1)。",
                "最小亮灯数是尽量同类配对；只有 cnt0 和 cnt1 都为奇数时必须剩下一对异类。",
                "因此最小值为 cnt0 mod 2。",
            ],
            "solution_brief": "关键观察：未知连线等价于把 2n 个开关任意两两配对。异类配对贡献一盏亮灯；最大异类配对数是 min(cnt0,cnt1)，最小异类配对数只由奇偶决定，为 cnt0%2。",
            "primary_topic": "基础实现与模拟",
        },
        "2039G": {
            "statement_brief": "给树上每个点赋 1..m 的值，要求任意路径上的 lcm 不被路径点数整除，且所有点值 gcd 为 1；求合法赋值数。",
            "transformed_statement": "把题目先看成：每个点 u 的值不能被任何不超过 h_u 的质数整除，其中 h_u 是经过 u 的最长简单路径长度。",
            "key_observations": [
                "若 a_u 是某个 k<=h_u 的倍数，就能找到长度 k 的路径让 lcm 被 k 整除，非法。",
                "这个条件等价于 a_u 不被任何 <=h_u 的质数整除，且它也是充分条件。",
                "再用 gcd=1 做莫比乌斯反演，并按 floor(m/g) 分块计算带 good 谓词的 μ 前缀和。",
            ],
            "solution_brief": "关键观察：路径约束可先变成每个点的局部禁质数条件。算出 h_u 后，u 可取的数必须避开所有 <=h_u 的质因子；全局 gcd=1 再通过 μ(g) 反演。由于 floor(m/g) 取值很少，按商分块求乘积贡献，μ(g)*good(g) 的前缀和用变体卷积/筛法维护。",
            "primary_topic": "数论与同余",
        },
        "2046E1": {
            "statement_brief": "给若干城市组的参赛者，每人有 strength、specialization、wisdom；要构造至多 5n 道不同专题题，使编号小的城市所有人解题数都严格多于编号大的城市，简单版 m=2。",
            "transformed_statement": "把题目先看成：每个城市组的 strength 区间必须近似按城市顺序分离；相邻组重叠时只能靠专属专题题补差。",
            "key_observations": [
                "若第 i 组最低 strength 不大于第 i+2 组最高 strength，中间至少要差 2 题但专题最多补 1 题，直接无解。",
                "相邻两组不重叠时，加少量无专题碰撞的普通难度题即可维持顺序。",
                "相邻重叠时，强组交叠成员必须通过自己的 specialization 解专属题，同时禁止弱组也解到。",
            ],
            "solution_brief": "关键观察：构造题目不是任意凑，而是先看每组 strength 的区间 [l_i,r_i]。跨两组仍交叠会让严格差距无法实现；只剩相邻组需要处理。m=2 时情况少：不交叠就放两道区间难度题，交叠就给强组交叠成员安排可由 wisdom 支撑的专属专题题。",
            "primary_topic": "构造与贪心",
        },
        "2046E2": {
            "statement_brief": "给任意 m 个城市组的参赛者，构造至多 5n 道不同专题题，使城市编号越小的所有参赛者解题数严格越多，或判无解。",
            "transformed_statement": "把题目先看成：城市组 strength 区间要形成只允许相邻冲突的链；每个冲突再转成专题和难度的避让约束。",
            "key_observations": [
                "若 l_i<=r_{i+2}，第 i 组和第 i+2 组之间无法拉开足够解题数差距。",
                "每个相邻冲突会禁止一批专题/难度区间，题目难度应尽量取高再向下调整。",
                "困难版要在线维护可用专题和难度禁区，保证总题数仍为 O(n)。",
            ],
            "solution_brief": "关键观察：先用每组 strength 的最小/最大值做全局可行性剪枝，保证只需处理相邻组。对相邻组，若区间交叠，就必须为强组成员放专属专题题，同时避开弱组可能凭 strength 或 specialization 解到的区间；用集合维护未占用专题和可选难度，逐个冲突构造。",
            "primary_topic": "构造与贪心",
        },
        "2101E": {
            "statement_brief": "树上只把 s_i=1 的点作为完全图顶点，边权为树距；对每个起点，求最长 nice 路径长度，其中相邻边权必须至少翻倍。",
            "transformed_statement": "把题目先看成：nice 路径的边权指数增长，所以路径长度最多 O(log n)，可以反向做有限层 DP。",
            "key_observations": [
                "树上任意距离不超过 n-1，而 nice 路径每步至少翻倍，因此长度有对数上界。",
                "这种路径不可能成环，因为最后一条边比前面边长总和还大。",
                "反向定义 dp[步数][点]，再用重心分解和后缀最大值优化转移。",
            ],
            "solution_brief": "关键观察：先证明 nice 路径很短。由于边权不断翻倍，最多 log n 条边，且不可能回到已访问点。于是可以反向 DP：dp[i][v] 表示从 v 出发走 i 步时下一条边权的最大允许值；朴素 O(n^2 log n)，用重心分解维护距离条件下的前二大后缀值优化。",
            "primary_topic": "树结构",
        },
        "2110E": {
            "statement_brief": "每个声音有音量和音高；要把所有声音排成一个序列，使相邻声音只差一个维度，且任意连续三个声音不能有同音量或同音高，判断并输出顺序。",
            "transformed_statement": "把题目先看成：把音量放二分图左侧、音高放右侧，每个声音是一条边；合法音乐就是经过所有边一次的欧拉路径。",
            "key_observations": [
                "相邻声音共享音量或音高，等价于相邻边共享端点。",
                "不 boring 要求连续三条边不能共享同一端点，这正是欧拉路径中走过一个点后换到另一侧的自然结构。",
                "因此只需判断二分图是否存在欧拉路径，并输出边序。",
            ],
            "solution_brief": "关键观察：声音不是点而是边。用音量和音高建二分图，一个声音连接对应音量点和音高点；包含所有声音的 beautiful non-boring 序列就是图中的欧拉路径。检查奇度点和连通性后跑欧拉即可。",
            "primary_topic": "图论与网络流",
        },
        "2178F": {
            "statement_brief": "根树按子树大小奇偶给点染黑白；可切掉白点与父亲的边再重连并重新染色。求能得到多少棵满足白点都在某条根到点路径上的树。",
            "transformed_statement": "把题目先看成：删除所有“白点连父亲”的边后形成若干组件，操作只会改变组件之间的连接，不会改变组件内部。",
            "key_observations": [
                "每个组件恰好有一个白点，且是组件内离根最近的点；这是操作不变量。",
                "组件内部边永远不能被操作删除，因此真正可变的是组件树。",
                "被征服条件变成：组件树中白组件必须排列在一条根链上，再计数可连接方式。",
            ],
            "solution_brief": "关键观察：先把原树缩成组件。切掉所有白点到父亲的边后，每个组件有唯一白根；题解证明这一结构在所有操作下不变，所以操作只是在重连组件树。于是问题转成统计哪些组件树能让所有白点落在一条根到点路径上。",
            "primary_topic": "树结构",
        },
        "2178G": {
            "statement_brief": "圆上有 2n 个点和按顺序加入的 n 条弦；对每个前缀，判断每条弦是否都出现在偶数个“相邻弦两两相交”的链中。",
            "transformed_statement": "把题目先看成：所有计数只关心模 2；弦是否相交可以用端点区间上的异或查询表示。",
            "key_observations": [
                "若把一条弦的两个端点异或进树状数组，查询另一条弦端点区间即可得到它们是否相交。",
                "链数奇偶 f(i) 可用相交弦的 f 值异或转移。",
                "要判断每条弦出现次数是否全为偶数，用随机 XOR hash 表示集合的对称差，避免存 bitset。",
            ],
            "solution_brief": "关键观察：模 2 下相交关系很好维护。弦 i 的链结尾贡献等于所有与 i 相交的旧弦贡献异或；而“哪些弦被奇数次覆盖”这个集合用 64 位随机哈希的异或表示。两个树状数组分别维护链奇偶和集合哈希，即可每加一条弦更新答案。",
            "primary_topic": "数据结构",
        },
        "2201C": {
            "statement_brief": "给定合法括号序列 S，选择一个非空子序列并把所选字符循环右移；计数右移后 S 仍合法的子序列数。",
            "transformed_statement": "把题目先看成：右移只会影响“部分包含所选子序列”的前缀和，危险情况是把一个 '(' 移出前缀、把 ')' 移入前缀。",
            "key_observations": [
                "若某前缀不含所选下标或包含全部所选下标，括号数量不变。",
                "若最后一个被移入的字符是 '('，不会破坏合法性；若是 ')'，前缀和可能减少 2。",
                "定义以某个 ')' 结尾的非平凡子序列 DP，再用前缀和/双指针维护前缀和不低于 2 的区间。",
            ],
            "solution_brief": "关键观察：看前缀和变化。循环右移时，只有夹在两个被选位置之间的前缀会变化；危险只发生在末尾选中字符为 ')' 且某段前缀和少 2。令 DP_i 统计以 i 为关键右端的危险子序列，用前缀和最低值条件转移，最后把末尾为 '(' 的任意子序列和末尾为 ')' 的合法 DP 相加。",
            "primary_topic": "组合计数与概率",
        },
        "2210F": {
            "statement_brief": "对排列区间 b，定义 beautiful 数组 c_i 可选前缀最大或前缀最小；问每个区间内 beautiful 数组最大逆序数。",
            "transformed_statement": "把题目先看成：选择前缀最大/最小对逆序的影响只在相同前缀最小值块内耦合。",
            "key_observations": [
                "选前缀最大不会和左侧形成逆序，只会压过右侧前缀最小。",
                "选前缀最小会和左侧大多数选择形成逆序。",
                "按相等前缀最小值分块后，各块可独立最大化，查询再用数据结构合并块贡献。",
            ],
            "solution_brief": "关键观察：对单个区间，先按前缀最小值相同的位置分块。不同块之间选择互不影响；一个块内最优形态是先选若干前缀最大、再选前缀最小，枚举切分可得块贡献。多询问版本维护这些块在区间中的贡献。",
            "primary_topic": "数据结构",
        },
        "2215D": {
            "statement_brief": "两枚棋子从位置 1、2 出发轮流向前跳 1..4 步到未染黑位置并得分；双方最优，求最终分差。",
            "transformed_statement": "把题目先看成：当领先棋子与落后棋子距离至少 6 时，领先者可以用连续小跳封锁落后者，后缀归领先者所有。",
            "key_observations": [
                "距离差达到 6 是吸收态：领先者能占住连续位置让对方无法越过。",
                "未进入吸收态时，只需记录两棋子距离 0..5 和中间 4 个位置的占用 mask。",
                "从后往前做博弈 DP，后缀和处理封锁后的收益。",
            ],
            "solution_brief": "关键观察：状态空间能小，是因为距离 >=6 后局面已经决定。领先者三次小跳可形成连续封锁，之后剩余后缀基本归领先者。于是 DP 只处理距离 <6 的局面，状态为领先方向、前后位置、4 位占用 mask，倒推最优分差。",
            "primary_topic": "动态规划与状态设计",
        },
        "2224A": {
            "statement_brief": "给数组 a；每个位置 i 至多操作一次，把 a_i 加上 a_{i+1}。求最终正数个数最大值。",
            "transformed_statement": "把题目先看成：从右往左决定是否把右侧值传给左侧；操作只改变左边，不会损害右边已经确定的正负。",
            "key_observations": [
                "若 a_{i+1}>0，把它加到 a_i 只会让 a_i 更大，不会让其它位置变差。",
                "若 a_{i+1}<=0，加上它没有帮助，跳过即可。",
                "因此从右到左贪心更新，最后统计正数。",
            ],
            "solution_brief": "关键观察：操作方向单向，只影响 a_i，不影响 a_{i+1}。所以从右往左看，若右边当前值为正，就把它传给左边；否则不传。每一步都是局部显然最优，最后数正数即可。",
            "primary_topic": "构造与贪心",
        },
        "2226D": {
            "statement_brief": "给数组，可反转任意一段，只要该段最小值与最大值之和为奇数。问能否通过若干操作把数组变成非降。",
            "transformed_statement": "把题目先看成：奇偶值分别要能在各自子序列内排序；异奇偶相邻反转可以作为交换工具。",
            "key_observations": [
                "若奇数子序列和偶数子序列都能各自排序，则整个数组可通过长度 2 的异奇偶反转排好。",
                "要改变同奇偶两个数的相对顺序，需要借助一个在数值上足够小或足够大的异奇偶数作缓冲。",
                "对奇偶子序列分别扫描，检查逆序处是否存在可用缓冲值。",
            ],
            "solution_brief": "关键观察：操作段可用当且仅当最小最大奇偶不同，因此异奇偶元素能帮忙交换。同奇偶内部若出现逆序，必须找到一个异奇偶值 z 在逆序两端之外，才能作为缓冲改变相对顺序；若所有逆序都能被缓冲修复，奇偶子序列分别可排序，答案为 YES。",
            "primary_topic": "构造与贪心",
        },
        "2228F": {
            "statement_brief": "给带点权树，选择一条恰好 k 条边的简单路径并删掉路径边，最大化分裂出的各连通块权值和的最小值；无路径则输出 -1。",
            "transformed_statement": "把题目先看成：二分答案 V，检查是否存在一条 k 边路径，使路径切开后每个相关组件权值都至少为 V。",
            "key_observations": [
                "V 越大越难，具备二分单调性。",
                "定根后，dp(x) 可表示从 x 向下延伸、且沿途切出的组件都满足 V 的最大路径长度。",
                "在每个点合并两个不同儿子的 dp，即可判断是否能形成 k 边路径；进一步可用排序/重心分解优化。",
            ],
            "solution_brief": "关键观察：把最大化最小组件权值改成判定。二分 V 后，DFS 维护每个点向下可延伸的最长合法腿；若两个儿子腿长之和加 2 达到 k，就找到了穿过当前点的合法路径。基础做法排序儿子 dp，优化版按子树权或重心分解降复杂度。",
            "primary_topic": "树结构",
        },
        "2240A": {
            "statement_brief": "构造 k 个非负整数，要求总和不超过 n，最大化这些数的 popcount 总和；只需输出最大值。",
            "transformed_statement": "把题目先看成：每个数的每个二进制 1 都要花费一个 2^b，而同一 bit 在 k 个数中最多放 k 次。",
            "key_observations": [
                "按贡献/花费看，每个二进制 1 的收益都是 1，成本是对应的 2^b。",
                "所以应优先购买最低位的 1。",
                "从低位到高位，每位最多买 k 个，直到预算 n 用完。",
            ],
            "solution_brief": "关键观察：这是买 bit，不是构造具体数组。第 b 位的一个 1 花费 2^b、收益 1，且最多给 k 个数各放一个。因此按 1,2,4,... 贪心买，当前位买 min(k, 剩余预算/2^b) 个即可。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2103A": {
            "statement_brief": "给定数组 a，求最大子序列长度，使存在两两不同的 y_i 让所有 x_i*y_i 都等于同一个常数。",
            "transformed_statement": "把题目先看成：漂亮子序列中的 x_i 必须两两不同，且只要两两不同就一定能构造 y。",
            "key_observations": [
                "若 x_i=x_j，则公共乘积 C 下会有 y_i=C/x_i=y_j，违背 y 两两不同。",
                "若所有 x_i 不同，取 P 为这些数的乘积，令 y_i=P/x_i，就能保证 y_i 也两两不同。",
                "因此问题只剩统计数组中不同值的个数。",
            ],
            "solution_brief": "关键观察：公共乘积条件把漂亮性完全等价为子序列元素互不相同。相同 x 会强制相同 y；不同 x 则用总乘积构造 y。答案就是 a 中 distinct 值数量。",
            "primary_topic": "基础实现与模拟",
        },
        "2143B": {
            "statement_brief": "有 n 个商品和 k 张优惠券；一张面值 x 的券覆盖恰好 x 个商品，其中最便宜的免费，求买完所有商品的最小花费。",
            "transformed_statement": "把题目先看成：先把商品价格降序排列，优惠券应覆盖一个前缀，并且短券排在长券前面，让免费商品尽量贵。",
            "key_observations": [
                "某张券覆盖的商品在降序价格中可调整成连续段，否则交换后能让免费商品不变差。",
                "所有被优惠券覆盖的商品应构成价格前缀，便宜后缀不值得优先占用券位。",
                "使用的券按面值升序排列；更短的券放前面，会让它免费掉更贵的商品。",
            ],
            "solution_brief": "关键观察：最优结构可由交换论证规整成唯一形态：商品按价格降序，选若干最短优惠券，按券面值升序依次覆盖前缀；每段里最后一个商品免费。若下一张券已经覆盖不了剩余商品就停止，剩下商品原价购买。",
            "primary_topic": "构造与贪心",
        },
        "2143D2": {
            "statement_brief": "给定序列 a，统计好子序列数量；好子序列要求能把下标染成红蓝，使每个逆序对两端颜色不同。",
            "transformed_statement": "把题目先看成：好子序列等价于最长下降子序列长度不超过 2，因此 DP 只需记录当前最大值和次大约束。",
            "key_observations": [
                "简单版三维 ways[i][mx][second] 会超时，困难版要去掉 i 维。",
                "处理 a_i 时，转移只会改 ways 矩阵中第 a_i 行或第 a_i 列的 O(n) 个位置。",
                "矩阵历史复制不需要真的复制，用每行/每列 Fenwick 树维护前缀和转移。",
            ],
            "solution_brief": "关键观察：不要保留每个 i 的整张 DP 表。由于“不选 a_i”只是复制上一层，直接原地维护 ways；“选 a_i”只影响一行或一列，用行 Fenwick 和列 Fenwick 查询前缀贡献并延迟更新即可，把 O(n^3) 降到 O(n^2 log n)。",
            "primary_topic": "动态规划与状态设计",
        },
        "2147C": {
            "statement_brief": "给定一排花盆，0 位置必须放兔子，兔子可朝左或朝右；若它面向的相邻格没有兔子且没有对向兔子冲突就会跳，问能否定向让所有兔子都不跳。",
            "transformed_statement": "把题目先看成：连续的 11 会把问题切开；剩下只需处理 1010...0101 这种交替块里的 0 个数奇偶。",
            "key_observations": [
                "子串 11 两侧的兔子互不影响，因此可以作为分割点。",
                "没有连续 0 的交替块可行当且仅当块内 0 的数量为偶数，可以成对安排 L/R 互相阻止。",
                "若出现连续 00，也能作为分割结构，把大块拆成若干奇偶更简单的小块；边界 0 可朝外看直接安全。",
            ],
            "solution_brief": "关键观察：不要把每只兔子单独 2-SAT。先用 11 和边界把串切成独立段；真正会卡住的是形如 1010...0101 且含奇数个 0 的段，它无法把兔子两两配成互相阻止。扫描这些交替段判断奇偶即可。",
            "primary_topic": "构造与贪心",
        },
        "2164C": {
            "statement_brief": "有若干把剑和怪物；剑伤害足够才能杀怪，杀后剑消失，若 c_i>0 会得到伤害 max(旧剑,c_i) 的新剑。求最多杀怪数。",
            "transformed_statement": "把题目先看成：先杀会返还新剑的怪，再处理不返还的怪；每一步都用当前能用的最小剑。",
            "key_observations": [
                "c_i=0 的怪不会产生新资源，因此最优一定放在所有 c_i>0 的怪之后。",
                "第一阶段按 b_i 从小到大处理 c_i>0 的怪；若能杀更难怪，就也能先杀更易怪，不会变差。",
                "每次使用能杀当前怪的最小剑，因为它留下的剑集合在排序意义上支配使用大剑的结果。",
            ],
            "solution_brief": "关键观察：题解的几个 lemma 都在证明同一个贪心结构：返剑怪优先、按生命值升序、用最小可行剑。第一阶段用小根堆维护剑，不能杀返剑怪的剑暂存到第二阶段；第二阶段对 c_i=0 怪排序后用 set/双指针继续匹配最小可行剑。",
            "primary_topic": "构造与贪心",
        },
        "2173F": {
            "statement_brief": "非增数组 a 上有 q 个区间询问；从 l 到 r 累加碎片大小，累计值达到阈值 x 就清零，问清零次数和最后剩余和。",
            "transformed_statement": "把题目先看成：每次清零形成的段长在非增数组里不会变短，因此可以按短段预处理、长段直接跳。",
            "key_observations": [
                "由于 a 非增，若某次达到 x 需要 len 个元素，后续从更靠右开始达到 x 只会需要不小于 len 的长度。",
                "把段长 <=B 的情况预处理成 f[x编号][len]，回答时可按 len 批量跳过很多段。",
                "段长 >B 时每跳一次至少前进 B，所以直接二分下一个达到 x 的位置也只会跳 O(n/B) 次。",
            ],
            "solution_brief": "关键观察：非增性让“达到阈值的段长”单调不减，这是整题的压缩点。离线离散化所有 x，对短段长预处理能从当前位置一次跳多少段；剩余长段用前缀和二分右端。取 B≈sqrt(n log n) 平衡两部分复杂度。",
            "primary_topic": "数据结构",
        },
        "2174C2": {
            "statement_brief": "长度 n 的随机颜色串，每个位置独立均匀选 m 种颜色；令 f 为非空回文子串数量，求 E[f^2] 模质数 p。",
            "transformed_statement": "把题目先看成：把 f 写成所有子串回文指示变量之和，平方后要统计一对回文子串同时成立的概率。",
            "key_observations": [
                "单个长度 s 的子串为回文的概率是 m^{-floor(s/2)}。",
                "两个子串同心时，同时为回文只等价于较长者为回文。",
                "两个子串不同心时，即使相交，回文约束仍可证明相互独立；固定两者长度和奇偶即可 O(n) 汇总贡献。",
            ],
            "solution_brief": "关键观察：E[f^2] 不是枚举所有颜色，而是枚举一对子串的回文事件。把子串对分为同心和不同心：同心看较长串，不同心事件独立，概率只由长度和奇偶决定。困难版再把非同心对按 s1+s2 与奇偶计数，前缀公式线性累加。",
            "primary_topic": "组合计数与概率",
        },
        "2201B": {
            "statement_brief": "有 1..n 各两张的记忆翻牌游戏，固定贪心策略总是翻最靠左的未知牌或已知配对牌；要求构造牌面顺序，使贪心恰好 k 回合完成。",
            "transformed_statement": "把题目先看成：每个数字的第一次出现记为 u，第二次出现记为 s，贪心耗时由 u/s 模式决定。",
            "key_observations": [
                "每对牌至少需要 1 回合、至多贡献 2 回合，所以 k 大致在 [n,2n] 内。",
                "最浪费的是不同数字形成的 us 模式；单独的 s 或同数字 us 会降低平均浪费。",
                "用 uuusus...ususss 这类模式可以接近最大 2n-1，再按 k 调整前缀结构。",
            ],
            "solution_brief": "关键观察：不需要模拟所有翻牌细节，只要控制每个数字的 u/s 出现形态。把牌序转成 u/s 串后，每种局部模式对回合数有固定贡献；先构造最大浪费模式，再把若干 us 改成更省回合的相邻配对，就能得到任意合法 k。",
            "primary_topic": "构造与贪心",
        },
        "2208B": {
            "statement_brief": "队列前 k 张牌可被打出并放到队尾；有一张目标牌和总能量 m，求最多能打出目标牌多少次。",
            "transformed_statement": "把题目先看成：目标牌不在前 k 时，必须先打掉它前面 x-k 张牌；为了省能量，只打这些前置牌里最便宜的若干张。",
            "key_observations": [
                "若目标牌在前 k，立刻打目标牌一定最优。",
                "若目标牌在位置 x>k，下一次能打到它之前，至少要打 x-k 张位于它前面的普通牌。",
                "选择前置牌中费用最小的 x-k 张可以达到这个下界，因此每轮目标牌间隔成本固定可算。",
            ],
            "solution_brief": "关键观察：最优策略很简单：目标牌可打就打，否则打当前前 k 张中费用最低的牌。第一次打目标前的最低成本 A 是初始目标前 p-k 张最便宜牌之和；之后每次目标回到队尾，再打到它的最低间隔成本 B 是非目标牌中 n-k 张最便宜牌之和。用预算直接套公式。",
            "primary_topic": "构造与贪心",
        },
        "2081F": {
            "statement_brief": "构造 n×n 矩阵，使每行每列都是 0..n-1 的排列，关于水平/垂直中线互补为 n-1，且所有相邻有序数对互不重复；无解则输出 NO。",
            "transformed_statement": "把题目先看成：奇数 n 除 1 外无解；偶数 n=2m 时，把每对数 (2i-2,2i-1) 沿四条对角折线路径交替填入。",
            "key_observations": [
                "奇数阶矩阵中心格会要求 a+a=n-1，除 n=1 外无法同时满足排列和互补结构。",
                "偶数阶按四条对角路径绕边填每一对相邻数字，可保证每行每列各出现一次。",
                "再把数字对 i 与 m-i 的路径做中线对称，就能满足互补；相邻有序对唯一性由路径类别和奇偶分类保证。",
            ],
            "solution_brief": "关键观察：这题不是搜索矩阵，而是找对称铺法。n 为偶数时，把数字按 (0,1),(2,3)... 成对，每对沿四段 45 度路径交替填；对应的高位数字对放在中线镜像位置。这样行列排列、水平/垂直互补和相邻有序对不重复同时被路径结构保证。",
            "primary_topic": "构造与贪心",
        },
        "2063F1": {
            "statement_brief": "给定平衡括号串和逐步加入的 good pair；每次已知若干 good pair 后，求与这些信息相容的平衡括号序列数量。",
            "transformed_statement": "把题目先看成：已知 good pair 会把括号位置切成若干最小平衡子序列，每块可独立填成任意平衡括号结构。",
            "key_observations": [
                "good pair 正是栈匹配算法中一起弹出的那一对括号。",
                "一对 good pair 的内部和外部都必须分别是平衡括号序列。",
                "简单版每次重新跑改造后的栈算法，找到所有最小平衡块，答案乘上各块长度对应的卡特兰数。",
            ],
            "solution_brief": "关键观察：不要猜整个括号树。把当前已知 good pair 当作切割边；用栈算法弹出时收集被切出的最小平衡子序列。每个长度为 2t 的未知块有 C_t 种填法，各块独立相乘。简单版数据小，更新后直接 O(n) 重跑即可。",
            "primary_topic": "组合计数与概率",
        },
        "2248G": {
            "statement_brief": "有若干商品价格和返利门槛；每次购买可花费一个可凑出的金额 x 并获得对应返利。对每个初始余额 h≤s，判断能否经过有限次购买使余额变成 0。",
            "transformed_statement": "把题目先看成：一次购买就是让余额变化 r(x)-x；低于最小净增长金额时只能下降，高于它时可无限增大但模某个 gcd 不变。",
            "key_observations": [
                "先用无界背包 bitset 求出所有可凑出的花费 x，以及对应净减少 d=x-r(x) 或净增加 r(x)-x。",
                "净增长阈值以下，余额只会下降，做 DAG 可达 DP；对同一个下降量只保留最小花费最灵活。",
                "一旦能做净增长购买，余额可变得任意大，之后是否能到 0 只由所有净变化和商品 gcd 形成的模不变量决定。",
            ],
            "solution_brief": "关键观察：余额转移分成两区。低区没有净增长，直接做下降可达性；高区可以反复做净增长把余额抬高，因此可达性变成同余问题。计算所有净增/净减和商品价格的 gcd，余额 i 在高区可归零当且仅当 i≡0 mod gcd 且存在能进入低区并归零的通道。",
            "primary_topic": "动态规划与状态设计",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2109D": {
            "statement_brief": "给定无向连通图和一个步长多重集 A；每次选一个 k 走恰好 k 条边。对每个点独立判断能否从 1 号点出发、使用 A 的某个子多重集走到它。",
            "transformed_statement": "把题目先看成：走到某点只关心总步数的奇偶和是否足够长，因为任意走法都能插入来回边多走 2 步。",
            "key_observations": [
                "对每个点只需知道从 1 到它的最短偶长度和最短奇长度，可在状态图上 BFS 得到。",
                "若使用所有步长，总和为 S，则能覆盖奇偶为 S mod 2 且距离不超过 S 的点。",
                "若要换奇偶，只能删去一个奇数步长；删最小奇数损失最少。",
            ],
            "solution_brief": "关键观察：图上的 walk 可以通过来回走边把长度增加 2，所以距离只分偶/奇两类。先 BFS 求 dist[v][0/1]；设 S=sum(A)，若 dist[v][S%2]<=S 则可达，否则检查是否存在最小奇数 o 且 dist[v][1-S%2]<=S-o。",
            "primary_topic": "图论与网络流",
        },
        "2240B": {
            "statement_brief": "给定 n,m,r,c，统计有多少个 n×m 的 0/1 矩阵，使每个 r×c 子矩阵的异或和都为 0。",
            "transformed_statement": "把题目先看成：这些条件是一组 GF(2) 线性方程；只要任意填上上边 r-1 行和左边 c-1 列，其余格子都会被唯一确定。",
            "key_observations": [
                "每个 r×c 子矩阵异或为 0，可以用已知的其它格子反推出右下角新格子。",
                "自由变量正好是上边 r-1 行与左边 c-1 列的并集。",
                "自由度为 nm-(n-r+1)(m-c+1)，答案是 2 的自由度次方。",
            ],
            "solution_brief": "关键观察：把矩阵约束看成线性方程组。先任意填前 r-1 行和前 c-1 列；随后从左上到右下，每个新 r×c 窗口都会唯一决定它的右下角格子。于是只需快速幂计算 2^{nm-(n-r+1)(m-c+1)}。",
            "primary_topic": "组合计数与概率",
        },
        "2202A": {
            "statement_brief": "从 (0,0) 出发，每步只能走 (+2,+1)、(+3,0)、(+4,-1)，判断能否到达给定整点 (x,y)。",
            "transformed_statement": "把题目先看成：(+2,+1) 和 (+4,-1) 同时使用没有必要，因为它们合起来等价于两次 (+3,0)。",
            "key_observations": [
                "若用 a 次上斜步、b 次平步、c 次下斜步，则 x=2a+3b+4c，y=a-c。",
                "上斜步和下斜步可以成对替换为两次平步，所以只需用一种斜步调 y。",
                "等价判定为 x+y 能被 3 整除，且 -x/4 <= y <= x/2。",
            ],
            "solution_brief": "关键观察：两种斜步同时出现可以消掉，转成两次平步。于是先用斜步把 y 调出来，再看剩余 x 是否能由 (+3,0) 补齐；整理后就是判定 x+y≡0 mod 3 且 y 在 [-x/4, x/2] 内。",
            "primary_topic": "数论与同余",
        },
        "2196F": {
            "statement_brief": "给 n,m，构造一个 n 点 m 边简单无向图，使顶点不能划分成两组且两组度数和相等；无解则输出 No。",
            "transformed_statement": "把题目先看成：先构造度数尽量平均的图，再保证不存在某个顶点子集度数和正好为总度数一半。",
            "key_observations": [
                "对奇数 n，把 2m 写成 qn+r，可尝试度数为 q 和 q+1 的近似正则图。",
                "若存在等和划分，就会有 qa+(q+1)b=m；这个方程可用不等式排除很多情况。",
                "一般情况先不断隔离两个 0 度点，把问题降到一个可构造的奇数规模核心。",
            ],
            "solution_brief": "关键观察：题解不是乱连边，而是先指定度数序列。奇数 n 时用环上连近邻的方法构造 q/q+1 度近似正则图，再通过 qa+(q+1)b=m 的无解性保证不可平分；若当前 n 太大，就隔离两个点递归缩小到满足判定的核心规模。",
            "primary_topic": "图论与网络流",
        },
        "2029G": {
            "statement_brief": "从全 0 数组出发，已做若干前缀/后缀加一操作；之后可继续做任意操作。给定多个 v，求最终让 a_i=v 的位置权值和最大值。",
            "transformed_statement": "把题目先看成：真正有用的位置只有 O(V) 个；值超过 V 或相邻值相同的位置可以删掉/合并权值。",
            "key_observations": [
                "前缀/后缀操作只通过当前位置被多少 L/R 覆盖影响最终值。",
                "对单个 v，可设状态记录当前位置处仍覆盖的前缀操作数和后缀操作数，用二维前缀最大优化。",
                "要同时回答所有 v，需要改写 DP 状态，让转移按 a_i+j 这类量用 Fenwick 树维护。",
            ],
            "solution_brief": "关键观察：先压缩位置，避免 n、m 进入复杂度。对固定 v，dp 只关心到当前位置时还有多少前缀/后缀增量覆盖它，转移是二维偏序最大值；进一步把状态变形后，用一维 Fenwick 维护两种符号情况，就能批量得到 1..V 的答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2023E": {
            "statement_brief": "给一棵树，要选尽量少的简单路径，使每个节点处任意两条相邻边都至少被某条路径同时经过。",
            "transformed_statement": "把题目先看成：每个子树向父亲返回若干条“还没配对完、需要往上接”的路径端，父节点负责把这些端点两两合并。",
            "key_observations": [
                "DFS 退出子树时，只需返回三元组：当前答案、向上端点数、可拆成两条向上路径的 bonus。",
                "在节点 v，要先把每个儿子的向上端点补到至少 deg(v)-1，才能覆盖 v 处相邻边对。",
                "若最大端点数不超过总端点数一半，就能几乎全部两两配掉；否则要优先用 bonus 增加其它儿子端点。",
            ],
            "solution_brief": "关键观察：路径覆盖的局部需求是“在同一节点相遇的边对要被连接”。子树只需向上暴露端点数量和可拆 bonus；父节点把各儿子的端点配对，若某个儿子端点过多，就用其它儿子的 bonus 补平后再合并。这个贪心三元组等价于压缩后的 DP 状态。",
            "primary_topic": "树结构",
        },
        "2223C": {
            "statement_brief": "根树每个非叶节点的路牌按时间 m 对子节点数取模旋转；询问给定 m 从根出发最终会到哪个叶子。",
            "transformed_statement": "把题目先看成：沿根到某点的选择必须满足一串同余方程，能到达的时间集合可写成 m≡R mod M。",
            "key_observations": [
                "到达节点 u 后选哪个儿子由 m+根到 u 的路程时间 对 d_u 取模决定。",
                "向下走一层就是把已有同余和新的 mod d_u 约束合并，模数变为 lcm(M,d_u)。",
                "若 d_u 已整除 M，下一步儿子唯一，可直接压缩；否则 M 至少翻倍，压缩后深度只有 O(log V)。",
            ],
            "solution_brief": "关键观察：不要逐时间模拟路牌。对每个节点维护能到达它的时间同余类 m≡R mod M；若当前 d_u 被 M 覆盖，儿子已唯一，直接合并节点；否则 lcm 会至少翻倍，所以有效树深被 1e18 的 log 限制。查询时只需沿压缩树走很少层。",
            "primary_topic": "数论与同余",
        },
        "2122A": {
            "statement_brief": "判断是否存在一个非负整数网格，使所有从左上到右下的贪心路径都不是最大路径和。",
            "transformed_statement": "把题目先看成：1 行、1 列和 2×2 是无解小特例，其余尺寸都能嵌入一个 2×3 反例块。",
            "key_observations": [
                "若只有一条路径，贪心路径必然也是最大路径。",
                "2×2 中第一步只在右和下之间选更大者，因此贪心一定能走到最大两条路径之一。",
                "其它网格可把左上 2×3 填成固定构造，其余填 1，使贪心被局部大数诱导走错。",
            ],
            "solution_brief": "关键观察：这题只需要找最小反例模式。1×m、n×1 和 2×2 不可能；除此以外，在左上角放 [[1,2,3],[3,1,1]]，其余全 1，贪心会先吃眼前较大值但错过全局最大路径。",
            "primary_topic": "构造与贪心",
        },
        "2231C": {
            "statement_brief": "每次选一个数，偶数除以 2，奇数加 1；求把所有数变成相等所需的最少操作数。",
            "transformed_statement": "把题目先看成：每个初始数沿操作会形成一条很短的祖先链，目标值必须出现在所有链中。",
            "key_observations": [
                "任意数在 O(log a_i) 步内到达 1，之后只会在 1 和 2 之间循环。",
                "对每个数枚举到达 1 前的所有值及步数，统计每个值被多少数到达、总步数多少。",
                "能作为最终公共值的 x 必须被 n 条链都到达，取总步数最小者。",
            ],
            "solution_brief": "关键观察：不要猜最终值。把每个 a_i 反复执行“奇加一、偶除二”，记录它到达各值的最早步数；所有数都能到达的值才是候选，答案是这些候选的步数和最小值。链长只有 O(log C)，所以总复杂度 O(n log C)。",
            "primary_topic": "构造与贪心",
        },
        "2174A": {
            "statement_brief": "重排字符串 t，使 s 至少作为一个子序列出现，并在所有可行重排中字典序最小；若无法包含 s 则输出 Impossible。",
            "transformed_statement": "把题目先看成：先从 t 中扣掉构成 s 的字符，剩余字符排序后与 s 做一次最小字典序归并。",
            "key_observations": [
                "若 t 中某字符数量不足以覆盖 s，直接无解。",
                "剩余字符排序得到 t'，因为它们不受子序列顺序约束，应尽量小地插入 s 的缝隙。",
                "逐位比较 s 当前字符和 t' 当前字符；相等时优先取 s，才能更早保住 s 的子序列结构并不变差。",
            ],
            "solution_brief": "关键观察：先保证 s 的字符被完整保留，再把所有多余字符排序。最终串就是把固定顺序的 s 和有序串 t' 做贪心 merge：每次取较小的首字符，相等取 s。若后面首次不同处 s 更小，提前取 s 更优；若 t' 更小则排序性会处理。",
            "primary_topic": "字符串",
        },
        "2135F": {
            "statement_brief": "给满二叉树，每个叶子函数为 x，内部节点函数为左子函数的右子函数次方；按 x→∞ 比较所有节点函数大小，并输出排名排列。",
            "transformed_statement": "把题目先看成：所有函数都是幂塔；比较两个幂塔时，取对数后变成比较指数中若干子幂塔的降序字典序。",
            "key_observations": [
                "父节点函数一定严格大于子节点函数，因此可以从叶到根拓扑处理排名。",
                "一个节点的比较信息等价于它指数部分包含哪些已排名的子幂塔。",
                "用持久化线段树维护排名频次和哈希，比较两个节点时二分找到第一个不同排名。",
            ],
            "solution_brief": "关键观察：数值巨大不能算，只能比较结构。把 f_u 看成 x 的幂塔表达式；两个内部节点比较时，把指数里的幂塔按大小排序后做字典序比较。由于子节点排名先于父节点确定，可自底向上插入节点，用持久化线段树哈希支持快速字典序比较。",
            "primary_topic": "树结构",
        },
        "2133F": {
            "statement_brief": "一排怪物，第 i 个爆炸会杀死距离 i 小于 e_i 的所有存活怪物，死怪不能再引爆；求最少引爆次数杀光所有怪物并输出方案，或判无解。",
            "transformed_statement": "把题目先看成：每个可引爆怪物对应一个覆盖区间，但两个被选区间的中心不能互相落在对方爆炸范围内。",
            "key_observations": [
                "这类似最少区间覆盖，但若两个区间中心相交，先引爆的会杀死另一个，不能同时选。",
                "只需保留“右端覆盖到哪里且最右选中中心是谁”的 DP 状态，进一步可压成一维 dp[i]。",
                "转移分两类相对位置，用线段树做区间最小值查询；重构后按爆炸威力升序引爆避免互杀。",
            ],
            "solution_brief": "关键观察：区间覆盖多了“中心不能互杀”的限制。令 dp[i] 表示选择 i 作为最右引爆怪，能覆盖到 i+e_i-1 的最少次数；合法前驱只落在两段区间里，因此线段树做两次 RMQ 即可转移。方案重构后按 e_i 升序引爆，保证前面的爆炸不会提前杀死后面要用的怪。",
            "primary_topic": "动态规划与状态设计",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2097C": {
            "statement_brief": "三角形区域内有一架飞机按固定速度飞行，碰到边界会镜面反射；判断它是否会恰好到达某个顶点逃出，并求逃出前反射次数。",
            "transformed_statement": "把题目先看成：把每次反射后的三角形展开到平面铺砖中，飞机不再反射，而是在直线上穿过一系列镜像三角形。",
            "key_observations": [
                "反射展开后，所有可能逃出的顶点都落在形如 (nx,ny) 的格点上。",
                "逃出时间 t 满足 x+v_x t≡0 mod n 且 y+v_y t≡0 mod n，可用同余方程求最小非负 t。",
                "反射次数就是展开直线段穿过的竖线、横线、斜边平行线和斜边垂线数量之和。",
            ],
            "solution_brief": "关键观察：不要在三角形里逐次反射。把反射后的三角形全部铺开后，轨迹是一条直线；逃出等价于直线首次到达某个 n 倍格点。先约掉速度 gcd，再解两条同余方程得到最早时间，最后用终点所在格坐标公式统计穿过多少条边界线。",
            "primary_topic": "数论与同余",
        },
        "2062H": {
            "statement_brief": "给定 n×n 星点集合 S；对每个非空子集，允许在能连接至少 3 颗星的位置补星，定义最终最少星系数，求所有子集的该值之和。",
            "transformed_statement": "把题目先看成：一个星系可由其最小外接矩形表示；两个星系的外接矩形在 x 或 y 投影相交时就能合并。",
            "key_observations": [
                "持续合并投影相交的外接矩形后，得到的矩形集合是唯一的。",
                "若一个子集不能形成指定大矩形内的唯一星系，它一定能拆成若干投影互不相交的小矩形。",
                "按 x 方向做区间 DP，并用 y 投影 bitmask 和高维前缀和同时统计所有二维区间。",
            ],
            "solution_brief": "关键观察：补星操作的效果不是看具体星点，而是看星系外接矩形的投影是否相交。相交就能合并，不相交就必须作为不同星系保留。于是对每个矩形统计能形成唯一星系的子集数，非法情况拆成若干 x/y 投影不交的小矩形，用区间 DP + y 方向 bitmask 容斥计算。",
            "primary_topic": "组合计数与概率",
        },
        "2035G2": {
            "statement_brief": "给定若干二分查找测试 (x_i,k_i)，要求删掉最少测试后存在数组使剩余测试都正确；困难版还要统计能达到最少删除数的数组数量。",
            "transformed_statement": "把题目先看成：二分查找某个位置会访问一条固定 touch 路径，两个测试能否同时成立只由两条路径的分叉点和 k 值大小关系决定。",
            "key_observations": [
                "两个位置 i,j 的 touch 路径在它们之间的共同访问点就是类似 LCA 的分叉点。",
                "分叉点之后，两条路径不能继续共享访问点；差异部分分别落在 LCA 到 i、j 的区间内。",
                "把同一 LCA 的所有转移合并处理，并按 k_i 递增插入，能把 困难版降到 O(m log n) 级别。",
            ],
            "solution_brief": "关键观察：不要把每个测试两两比较。二分过程本身是一棵隐式决策树，测试 i 与 j 的冲突只发生在它们 touch 路径的分叉点附近。把转移按这个 LCA 分组后，dp 中真正同时依赖 i,j 的项只有很少的多项式表达式，可预存若干加权和批量转移。",
            "primary_topic": "动态规划与状态设计",
        },
        "2156B": {
            "statement_brief": "环上有 A/B 两类机器，A 让数减一，B 让数变成下取整一半；每个询问从机器 1 开始循环执行，求数变成 0 需要多少秒。",
            "transformed_statement": "把题目先看成：如果存在 B，数值每绕几步就会至少折半一次；只有全 A 的情况会退化成逐次减一。",
            "key_observations": [
                "若字符串全是 A，答案直接等于初始 a。",
                "只要有一个 B，数值至多经过 O(n log a) 次机器操作就会归零。",
                "进一步可把连续相同机器压成块，长 A 段一次性扣 min(cnt,a)，长 B 段一次性右移若干位。",
            ],
            "solution_brief": "关键观察：最坏的大 a 只在全 A 时麻烦，而全 A 的答案就是 a。其余情况下每轮至少遇到一个 B，数会反复折半，因此直接模拟机器操作也只有约 n·30 步；想优化常数就把连续 A/B 压成块批量处理。",
            "primary_topic": "基础实现与模拟",
        },
        "2143E": {
            "statement_brief": "给定括号串 s，可把相邻两个相同括号同时翻成另一种括号；求能否经过若干操作得到合法括号序列，并构造一个。",
            "transformed_statement": "把题目先看成：先翻转所有偶数位置的括号，原操作就等价于交换相邻两个不同括号，因此只保留左右括号数量。",
            "key_observations": [
                "偶位翻转后，操作 ()↔)(，可以视作任意相邻交换。",
                "所以能到达的状态只由翻转后左括号数和右括号数决定。",
                "合法括号串反推回翻转前，会要求翻转后的左右括号数量都为偶数，且不能没有左括号。",
            ],
            "solution_brief": "关键观察：操作原形很难看，先把偶数位括号全部取反。这样相邻相同翻转会变成相邻不同交换，等价于可以任意重排翻转后的括号。于是只需检查翻转后左右括号数量的奇偶和非空条件；可行时构造一个形如若干左括号、右括号、再交错的目标串并翻回去。",
            "primary_topic": "构造与贪心",
        },
        "2071E": {
            "statement_brief": "树上每个点独立以给定概率掉落，掉落点及其边被删除；求最终森林中叶子点无序对数量的期望。",
            "transformed_statement": "把题目先看成：用期望线性性枚举点对；两点成为叶子的事件只在相邻或共享邻居时不独立。",
            "key_observations": [
                "点对分三类：原树相邻、共享一个公共邻居、既不相邻也不共享邻居。",
                "第三类事件独立，贡献就是 leaf_u·leaf_v。",
                "前两类需要单独扣/加修正，但都能按边或按公共邻居线性汇总。",
            ],
            "solution_brief": "关键观察：不要枚举所有点对。先算每个点最终成为叶子的概率；远距离点对相互独立，可以用总和平方批量统计。只有相邻点对和距离为 2 的点对会共享随机变量，分别按边、按中间点计算特殊贡献并从总独立贡献里修正。",
            "primary_topic": "组合计数与概率",
        },
        "2067C": {
            "statement_brief": "每次可以给 n 加上 9、99、999 等只含数字 9 的正数，求最少多少次后十进制表示中出现数字 7。",
            "transformed_statement": "把题目先看成：若固定操作次数 k，每次加 99..9 等价于先把 n 减 k，再给某些十进制位各加 1。",
            "key_observations": [
                "答案不超过 9，因为连续加 9 会让个位完整循环。",
                "一次加 10^x-1；固定 k 次后，总效果等价于对 n-k 加 k 个 10^x。",
                "因此只需枚举 k=0..9，检查 n-k 的某一位能否通过不超过 k 次加一变成 7。",
            ],
            "solution_brief": "关键观察：直接分析加 999 对进位的影响很乱，但固定做 k 次后，每次 10^x-1 的 -1 可以先统一扣掉，剩下就是给某些位加 1。枚举 k，取 n-k 的所有位 digit，看 min((7-digit) mod 10) 是否不超过 k，第一个满足的 k 就是答案。",
            "primary_topic": "数论与同余",
        },
        "2057E1": {
            "statement_brief": "无向带权图上有询问 (a,b,k)，要在所有 a 到 b 路径中最小化路径边权排序后的第 k 大边权。",
            "transformed_statement": "把题目先看成：二分答案 x 后，边权大于 x 的边记为 1，其余记为 0；路径第 k 大边权不超过 x 等价于 1 边数量小于 k。",
            "key_observations": [
                "固定 x 后，只需求 a 到 b 的 0/1 最短路是否 < k。",
                "按边权从小到大把边从 1 改成 0，每次只需用新变轻的边更新全源最短路。",
                "简单版 n,m 小，可预处理 dp[t][i][j] 表示前 t 条最小边为 0 时的 0/1 最短距离。",
            ],
            "solution_brief": "关键观察：第 k 大最小化可以转成阈值判定。给阈值 x 后，重边数量少于 k 就说明第 k 大≤x。按边权排序逐步把边变轻，用 d'[i][j]=min(d[i][j],d[i][u]+d[v][j],d[i][v]+d[u][j]) 做 O(n^2) 更新，预处理后每个询问二分边权层数。",
            "primary_topic": "图论与网络流",
        },
        "2055F": {
            "statement_brief": "给定偶数面积的凸多连块，判断能否切成两个只允许平移后完全重合的连通多连块。",
            "transformed_statement": "把题目先看成：若能切成两个平移同构块，切线在边界上会形成强约束；固定纵向偏移 k 后，另一半形状几乎被唯一确定。",
            "key_observations": [
                "合法划分得到的两块也必须是凸的，否则两个非凸块无法拼成原凸块。",
                "除水平/竖直直切外，斜向切割的边界只能单调向右上或右下走。",
                "固定 k 后可由行宽差分递推出候选半块；哈希/前缀和先筛掉绝大多数 k，再逐个验证。",
            ],
            "solution_brief": "关键观察：不要枚举每个格子怎么归属。看周长结构：有效斜切会把外周分成几段两两平移相同的边界，左边界分割点必须是 0,k,2k。固定 k 后，半块第 i 行宽度满足交错差分式 b_i=a_i-a_{i-k}+a_{i-2k}-...；先用周长哈希或面积条件快速筛 k，再检查候选半块是否真可行。",
            "primary_topic": "几何",
        },
        "2219D": {
            "statement_brief": "根树每个点有 0..n-1 的排列权值，f(v) 是根到 v 路径权值集合的 MEX；至多把一个点权改成它自己的 f(v)，最大化所有 f(v) 之和。",
            "transformed_statement": "把题目先看成：MEX 是第一个空槽；操作是在某个子树的所有路径集合中，把 p_v 这个 token 挪到 f(v) 这个空槽。",
            "key_observations": [
                "若 p_v<f(v)，操作只会让子树内 MEX 变小，没有意义。",
                "对子树点 x，操作后的 MEX 只会变成 min(g(x),p_v) 或 min(f(x),p_v)，其中 g(x) 是第二个空槽。",
                "按 p_v 从大到小处理，用树上子树加/查维护 f、g 小于当前阈值的和与数量。",
            ],
            "solution_brief": "关键观察：把 MEX 想成无限槽位里的第一个洞。对 v 操作会在整个 v 子树中搬走 p_v 槽的 token、填上 f(v) 槽，因此每个 x 的新 MEX 只有两种公式，取决于 x 路径上是否已有 f(v)。按 p_v 降序扫，并用欧拉序 + Fenwick 维护子树内 f/g 的阈值统计即可算每个操作收益。",
            "primary_topic": "树结构",
        },
        "2133C": {
            "statement_brief": "交互题：隐藏一张 DAG；询问给定集合 S 和起点 x 时，返回只在 S 内从 x 出发的最长路径长度。要求用 2n 次询问找一条最长路径。",
            "transformed_statement": "把题目先看成：先问每个点在全图中的最长路径长度，把点按长度分层；最长路径每走一步层数必然减一。",
            "key_observations": [
                "对每个点 x 询问全体点，可得到从 x 出发的最长路径长度。",
                "选长度最大的点作为起点；若当前层数为 k，下一个点必须在 k-1 层。",
                "用二点集合 {当前点,候选点} 询问是否返回 2，就能确认当前点是否能直接走到候选点。",
            ],
            "solution_brief": "关键观察：第一次 n 个询问已经给出所有点的“深度标签”。最长路径从最大标签开始，每条边都应走向标签小 1 的点。之后只在下一层候选中用二点询问找能接上的点；每个候选最多被试一次，总询问数不超过 2n。",
            "primary_topic": "交互",
        },
        "2116A": {
            "statement_brief": "两名玩家和各自骑士都有生命值；奇数回合先手骑士行动，偶数回合后手骑士行动，可攻击对方本人或骑士，双方最优求胜者。",
            "transformed_statement": "把题目先看成：一个玩家只要本人或骑士任一生命值先归零，就失去胜利能力；因此每边的有效生命是 min(本人,骑士)。",
            "key_observations": [
                "杀死骑士后，对方以后无法攻击，等价于已经锁定胜局。",
                "所以攻击对方较小生命目标总不劣。",
                "先手每轮先行动，若 min(a,c)>=min(b,d) 则 Gellyfish 能先击破对方关键目标，否则 Flower 获胜。",
            ],
            "solution_brief": "关键观察：不要展开博弈树。本人死会输，骑士死也会因无法再攻击而必输，所以每方真正的耐久是本人和骑士生命的较小值。双方都应打对方较小的那个目标；先手在平局时先击杀，因此判断 min(a,c) >= min(b,d)。",
            "primary_topic": "博弈",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2089E": {
            "statement_brief": "给一棵 DFS 序编号的根树。第 i 天可选择一个尚未坍塌的点并使其整棵子树坍塌，同时编号 n-i+1 的点也会自动坍塌；对每个 i，统计恰好探索 i 天且最后一次探索为根的方案数。",
            "transformed_statement": "把题目先看成：第 i 天选择的点被放到序列位置 n-i+1；一个点 u 只能放在位置 u 或之后，DFS 子树区间外的位置决定了它能否留给祖先或放到子树之后。",
            "key_observations": [
                "DFS 序让每棵子树变成连续区间 [l,r]，子树内的点不能放到 l 之前。",
                "放到 r 之后的点只需要满足父子先后关系，可作为“后置操作”传给祖先合并。",
                "DP 需要同时记录留给祖先的位置、子树内部空位数、需要放到子树之后的点数；合并儿子时，DFS 序靠前儿子的后置操作可以填入靠后儿子的空位。",
            ],
            "solution_brief": "关键观察：自动坍塌使普通子树背包失效，必须把“第几天选点”反过来看成把点放进位置 n-i+1。DFS 序保证子树是区间，于是每个子树只需维护空位、后置点和是否留祖先位；按儿子 DFS 序反向合并，就能精确处理后置操作填入后面子树空位的组合数。",
            "primary_topic": "树结构",
        },
        "2066D1": {
            "statement_brief": "n 层楼每层一人依次投纸飞机；第 i 层能看到 1..i 层投出的飞机，看到至少 c 架后就不再投。简单版投掷记录全缺失，已知总共投了 m 架且每人最终至少看到 c 架，求补全记录方案数。",
            "transformed_statement": "把题目先看成：一楼能看到所有飞机，所以一楼的投掷只能出现在前 c 次；枚举一楼投了几次后，其余楼层变成同型子问题。",
            "key_observations": [
                "第 c+1 到第 m 次不可能由一楼投出，否则一楼早已看到 c 架。",
                "若一楼投了 k 次，这 k 个位置可在前 c 次中任选，贡献组合数 C(c,k)。",
                "删掉一楼和这 k 次投掷后，其余记录等价于 n-1 层、m-k 次的同一个问题。",
            ],
            "solution_brief": "关键观察：按最低楼层剥离。枚举一楼在前 c 次中出现 k 次，有 C(c,k) 种放法；这些飞机对更高楼层的“看到数量”没有区别，可以直接忽略，剩下就是规模 (n-1,m-k) 的子问题。于是 dp[i][j]=Σ C(c,k)·dp[i-1][j-k]。",
            "primary_topic": "组合计数与概率",
        },
        "2057G": {
            "statement_brief": "给一个由自由格组成的网格图，设自由格数为 s、边界周长为 p。要求构造集合 S，使 |S|≤(s+p)/5，且每个自由格要么在 S 中，要么与 S 中某格相邻。",
            "transformed_statement": "把题目先看成：要找一个小的支配集。用 (x+2y) mod 5 把无限网格染成 5 类，每个格子及其四邻恰好落在 5 个不同颜色中。",
            "key_observations": [
                "令 T_i 为颜色 i 的自由格，五个 T_i 的大小总和正好是 s。",
                "若某自由格没有被 T_i 覆盖，就把它加入 D_i；这些缺口可和边界边一一对应。",
                "五个 S_i=T_i∪D_i 的总大小为 s+p，因此必有一个大小不超过 (s+p)/5。",
            ],
            "solution_brief": "关键观察：不是贪心找支配集，而是用 5 染色做平均。颜色 i 自带覆盖大部分格子，漏掉的格子只会因为对应颜色落在外部邻格上，这些漏项总数刚好由边界周长 p 支付。五个候选集合总大小 s+p，取最小的那个即可。",
            "primary_topic": "构造与贪心",
        },
        "2189F": {
            "statement_brief": "树上每点有若干坚果。一次操作选择点 v，所有其它有坚果的点各有一颗坚果向 v 方向移动一步，花费 p；最后按仍有坚果的点数吃掉，每点花 q。求最小总花费。",
            "transformed_statement": "把题目先看成：操作结束后仍然有坚果的活点集合一定是一棵连通子树 L；L 外的操作都可替换成 L 内操作。",
            "key_observations": [
                "任意时刻正坚果点的连通闭包可以用“活点集合”刻画，最终保留集合 L 连通。",
                "最后一次在 L 外做的移动可以换成在 L 内做，不会让 L 外点重新变成需要吃的点。",
                "固定最终 L 后，只需计算让 L 外各方向全部死亡的最少操作数，再加上 q·|L|。",
            ],
            "solution_brief": "关键观察：不要模拟坚果流动，而是反过来枚举最终还要付 q 的连通子树。题解证明 L 外操作可替换到 L 内，所以最优方案只关心每条有向边两侧“把外侧全部清空”的最少次数。用边方向 DP 合并这些代价，最后在每个候选 L 上取 p·操作数+q·|L|。",
            "primary_topic": "树结构",
        },
        "2161H": {
            "statement_brief": "两个数组 a、b 合起来是 1..n+m 的排列。进行 k 次循环比较：若 a[i mod n] > b[i mod m] 则交换，求最终两个数组。",
            "transformed_statement": "把题目先看成：先按阈值 x 把数二值化为“小于 x”和“不小于 x”，解决 0/1 版本后，再随着 x 增大恢复每个具体数的位置。",
            "key_observations": [
                "0/1 版本中，b 里的 0 会像 token 一样按步长 m 在 a 的环上迁移。",
                "同一位置多个 token 相遇时，只保留时间最小的 token，其余 token 继续向后推。",
                "若 gcd(n,m)>1，环会分成若干独立类；互质时可重编号成每步 +1 的循环过程，再用周期和前缀最小维护。",
            ],
            "solution_brief": "关键观察：原排列过程可由所有阈值的 0/1 过程叠加恢复。对固定阈值，b 中的小数 token 按 +m 进入 a 环，同位置冲突只留下最早 token；最终哪些位置为小数确定后，阈值从小到大变化时每次只定位新增的那个数。核心是把巨大 k 的循环交换压成环上 token 推进和周期维护。",
            "primary_topic": "数据结构",
        },
        "2064A": {
            "statement_brief": "给二进制串 s 和空串 t；每次可把某个串的一个后缀移到另一个串末尾。求最少操作数，使最终 s 只含 0、t 只含 1。",
            "transformed_statement": "把题目先看成：每次移动一个后缀最多消掉一个相邻字符变化；如果 s 以 1 开头，还必须先把整串移到 t。",
            "key_observations": [
                "两个串中相邻不同对的总数是一个势能，每次操作最多让它减少 1。",
                "若 s 开头是 1，目标要求所有 1 在 t 中，必须额外做一次整串迁移。",
                "每次取当前第一个变化位置开始的后缀移到另一个串，能恰好每步减少一个变化。",
            ],
            "solution_brief": "关键观察：答案不是模拟所有后缀选择，而是数边界。初始 s 中每个 01/10 交界最终都要被一次操作切开，因此至少需要相邻不同次数；若首字符是 1，还要先整体搬一次。按第一个变化位置切后缀可以达到这个下界。",
            "primary_topic": "字符串",
        },
        "2062E2": {
            "statement_brief": "树上轮流选点并删除其子树；除先手第一步外，每次所选点权值必须大于对手上次所选点。不能操作的人获胜。困难版要求输出所有能让先手获胜的第一步点。",
            "transformed_statement": "把题目先看成：先手选点 v 后，必须防住后手每个可能的回复 u；对每个 u，只需知道子树外权值大于 w_u 的点的 LCA。",
            "key_observations": [
                "若先手第一步后子树外没有更大权值点，反而会让后手无路可走并获胜。",
                "对后手点 u，设 g(u) 为 u 子树外所有权值大于 w_u 的点的 LCA；先手点必须覆盖这些点或让 u 无法被选。",
                "按权值从大到小维护外部大权点集合，并对 u、g(u)、lca(u,g(u)) 到根的链做计数。",
            ],
            "solution_brief": "关键观察：困难版不要逐个第一步模拟博弈。枚举后手可能选的 u，先手 v 合法当且仅当对所有更大权值威胁，v 的子树能把它们一起删除，或 u 已经被 v 阻止。把“所有外部大权点”压成一个 LCA g(u)，再用按权值扫描和树链加统计哪些 v 满足全部约束。",
            "primary_topic": "树结构",
        },
        "2035G1": {
            "statement_brief": "给若干测试 (x_i,k_i)，要求删除最少测试后存在数组 a，使所有保留测试中的二分查找 k_i 都返回位置 x_i；同时统计达到最少删除数的数组数量。",
            "transformed_statement": "把题目先看成：按 x 排序后，能同时保留的测试必须让 k 严格递增；若 k=1，则它只能出现在 x=1。",
            "key_observations": [
                "若 x_i<x_j 但 k_i>k_j，二分查找过程中会在某个中点同时要求 a_m≥k_i 且 a_m<k_j，矛盾。",
                "反过来，k 递增且 k=1 的特例合法时，可以构造数组让这些测试全部通过。",
                "计数数组时，以最后保留测试为状态，转移贡献由两条 binary search touch 路径的重叠约束决定。",
            ],
            "solution_brief": "关键观察：先把“保留哪些测试”变成最长合法递增子序列问题。按 x 排序后，k 必须严格递增，且 k=1 只能在 x=1；这是充要条件。计数时 dp 枚举最后一个保留测试，两个测试之间能填多少数组值由二分访问过的中点集合决定，简单版直接 O(m^2 log n) 计算转移。",
            "primary_topic": "动态规划与状态设计",
        },
        "2257E": {
            "statement_brief": "有 n 个建筑项目，每层先支付 a 再获得 b，可任意交错施工；初始资金 x，求最终能达到的最高楼层，平手取编号最小。",
            "transformed_statement": "把题目先看成：先用所有总利润非负的连续楼层段尽量赚取资金，资金最大化后再逐楼尝试冲最高层。",
            "key_observations": [
                "单独某层可能亏钱，但一段连续楼层总利润非负时，跨过它会让资金不减少。",
                "每栋楼可分解成若干最短非负利润段，每段有一个进入所需最低资金门槛。",
                "总是先执行当前可负担且门槛最小的段；若最小门槛都负担不起，就没有任何非负段可继续赚资。",
            ],
            "solution_brief": "关键观察：先别急着找最高层，而是先把资金做大。把每栋楼从当前高度切成最短“总利润非负”段，并计算进入段内任意前缀都不爆仓的最低资金。用集合按门槛取当前可做段，做完加利润并插入下一段；资金最大化后，再对每栋楼从当前层逐层试，取最高和最小编号。",
            "primary_topic": "构造与贪心",
        },
        "2238B": {
            "statement_brief": "计数三元组 (a,b,c)，满足 gcd(lcm(a,b),lcm(b,c)) = gcd(a,c)，其中 1≤a,b,c≤n。",
            "transformed_statement": "把题目先看成：等式成立当且仅当 b 同时整除 a 和 c。",
            "key_observations": [
                "若 b|a 且 b|c，则 lcm(a,b)=a、lcm(b,c)=c，等式直接成立。",
                "反过来，两个 lcm 都被 b 整除，所以它们的 gcd 也被 b 整除。",
                "该 gcd 又等于 gcd(a,c)，因此 b 同时整除 a 和 c。",
            ],
            "solution_brief": "关键观察：把 lcm 的复杂式子抓住 b 这个公共因子。可行三元组恰好是 a、c 都为 b 的倍数；于是枚举 b，a 和 c 各有 floor(n/b) 种选择，贡献 floor(n/b)^2，总和 O(n)。",
            "primary_topic": "数论与同余",
        },
        "2219E": {
            "statement_brief": "在 n×n 棋盘放尽量多棋子；一个棋子攻击其右下矩形除自身外所有格，要求每个格子被攻击棋子数为偶数，并保证棋子数至少 3⌊n²/10⌋。",
            "transformed_statement": "把题目先看成：在模 2 下构造一个下三角区域的 0/1 填法，使局部递推 v[i][j]+v[i+1][j]+v[i][j+1]=0 成立。",
            "key_observations": [
                "合法性可化为上三角全 0，并在下三角满足三点异或递推。",
                "先用 i+j≥n-1 且 i≠j mod 3 的周期图案，密度约为 1/3，但对角附近有少量缺陷。",
                "缺陷可用 Pascal 三角形 mod 2 的局部图案修补，且修补区域可控，不会破坏主体密度。",
            ],
            "solution_brief": "关键观察：攻击偶性等价于一个模 2 局部方程。先构造密度足够高的周期填法，再只处理对角附近的方程缺陷；每个缺陷用 Pascal 三角形模 2 图案向一侧传播修补。这样既满足全部奇偶方程，又保留接近 1/3 的棋子密度。",
            "primary_topic": "构造与贪心",
        },
        "2187C": {
            "statement_brief": "特殊无交叉有向图上进行追逃游戏：Jerry 每回合必须沿出边走，Tom 可走可停，Tom 想抓到 Jerry 且最小化自己的移动次数。求所有起点对的最小移动次数之和。",
            "transformed_statement": "把题目先看成：每个点只保留能走到最远位置的出边，这些最远边形成一棵以 n 为根的树；追逃问题变成树上 LCA 公式。",
            "key_observations": [
                "由于额外边无交叉，走到更远的出边永远不劣；两人最优都只需走最远边。",
                "最远边构成一棵指向 n 的树，深度 d 表示到终点还要走几步。",
                "若 d(x)<d(y)，Tom 不用动也追不上；否则 Tom 移到 lca(x,y) 等 Jerry，贡献 d(y)-d(lca)。",
            ],
            "solution_brief": "关键观察：先把原 DAG 压成“每点最远出边”的树。无交叉性质保证走远边支配其它选择，所以游戏值只和这棵树的深度和 LCA 有关。所有点对贡献可拆成 min(depth)、LCA 深度、同深度修正三部分，分别用排序、子树大小和 dsu-on-tree 统计。",
            "primary_topic": "树结构",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2161C": {
            "statement_brief": "给 n 个商品价格和忠诚度因子 X，购买过程中当前总消费 S 的等级为 floor(S/X)。若买某件商品后等级上升，就获得该商品价格对应的积分；要求最大积分并输出购买顺序。",
            "transformed_statement": "把题目先看成：等级总共只会上升 floor(sum/X) 次，因此最多只能让这么多件商品计入积分，显然应尽量让最贵的这些商品触发升级。",
            "key_observations": [
                "每件商品价格不超过 X，所以一次购买最多让等级上升 1。",
                "能触发积分的商品数量固定上界为总价除以 X 的整数部分。",
                "从小到大排序后，若当前买最贵商品能跨过下一个等级就买它，否则买最便宜商品垫消费。",
            ],
            "solution_brief": "关键观察：积分次数的上限只由总价决定，最优就是让最贵的 floor(sum/X) 件商品触发升级。排序后双指针构造：能用当前最贵商品跨等级时就买最贵并计分，否则买当前最便宜商品垫 S。因为单件价格 ≤X，每次升级只会跨一层，这个贪心能达到上界。",
            "primary_topic": "构造与贪心",
        },
        "2155E": {
            "statement_brief": "n×m 网格上有若干棋子。每步选一个棋子沿列号不增的简单路径移到第 1 列并删除，路径内部会派生新棋子；两人轮流操作，判断最优胜者。",
            "transformed_statement": "把题目先看成：每个棋子最终贡献若干步数，只需要这些贡献的奇偶；n=1 和 n≥2 的奇偶规律不同。",
            "key_observations": [
                "n=1 时，位于第 c 列的棋子会递归派生前面各列棋子，总操作次数为 2^{c-2}。",
                "因此一行时只有第 2 列棋子贡献奇数步，其它列贡献偶数步或 0。",
                "n≥2 时，败态当且仅当所有第 2 列及之后的列棋子数都是偶数；若最高奇数列存在，当前玩家可移动它把所有低列奇偶调成偶数。",
            ],
            "solution_brief": "关键观察：这不是搜索游戏树，而是看各列棋子数奇偶。n=1 时只有第 2 列会改变总步数奇偶；n≥2 时，状态只看第 2..m 列是否全偶，全偶是败态，否则选最高的奇数列，通过路径派生数量把更低列调成全偶交给对手。实现上维护相关列奇偶即可。",
            "primary_topic": "博弈",
        },
        "2154E": {
            "statement_brief": "给正整数数组和 k 次以内操作。先固定一个奇数长度 x，每次选一个长度 x 的子序列，把其中所有数变成该子序列中位数；求最终数组和最大值。",
            "transformed_statement": "把题目先看成：排序后，最优方案可以只围绕同一个中位数 a_i 操作；固定中位数后，只需选择左右各取 y 个时的最佳 y。",
            "key_observations": [
                "若一次操作中位数为 a_i，最该被抬高的是最小的 y 个数，必须被压低的是 a_i 右侧连续 y 个数。",
                "若两个操作使用不同中位数 a_i<a_j，把它们都改成较大的 a_j 不会更差。",
                "固定 i 后，增大 y 的边际收益单调下降，边际损失单调上升，因此可二分最佳 y。",
            ],
            "solution_brief": "关键观察：先排序，并证明存在最优方案所有操作都用同一个中位数。固定 a_i 和 x=2y+1 后，k 次操作最多把前 min(ky,i) 个小值抬到 a_i，同时必须把 i 后 y 个值压到 a_i。这个收益关于 y 的边际单调下降，用前缀和枚举 i、二分 y 即可。",
            "primary_topic": "构造与贪心",
        },
        "2147F": {
            "statement_brief": "两名商人的偏好分别是一组排列；持有物品 i 时，若某商人认为 i 比 j 更有价值，就可换成 j。每次交换某个排列中的两个位置后，统计有序对 (i,j) 中 i 能否经若干交易换到 j。",
            "transformed_statement": "把题目先看成：物品按强连通分量排成一条链；值域 x 处能切开，当且仅当两个排列中 1..x 这批值占据同一组位置。",
            "key_observations": [
                "若一个物品在两排列中的名次区间跨过 x，则 x 不可能是强连通分量之间的切口。",
                "对每个物品，只需在它两种名次之间的值域区间加一，未被覆盖的位置就是切口。",
                "维护所有切口位置后，强连通分量大小由相邻切口距离得到，答案是基础可达对加上各分量内部双向可达对。",
            ],
            "solution_brief": "关键观察：交易图不用显式建边。强连通分量之间能在值域 x 切开，等价于两个排列里前 x 个值对应同一批物品；任一物品的两个排名夹住的值域都会禁止切口。每次交换只影响两个物品的禁止区间，用懒标记线段树维护覆盖最小值为 0 的切口及相邻距离平方和，就能更新答案。",
            "primary_topic": "数据结构",
        },
        "2097A": {
            "statement_brief": "每天航班登机方式只有两种。Vadim 与若干学生在日期 a_i 打赌，要提前预测 a_i+1 和 a_i+2 两天的方式；问是否存在策略保证至少赢一个学生。",
            "transformed_statement": "把题目先看成：每个日期的两个后继结果只有 4 种；若同一天有 4 个学生可覆盖全部结果，或有一段连续日期两端各至少两个学生，也能强行覆盖。",
            "key_observations": [
                "同一 a 出现 4 次时，可以给四个学生分别预测 00、01、10、11，必胜。",
                "若连续日期段 [x,y] 中两端各至少出现两次，中间每天至少出现一次，可用端点和中间预测构造夹逼。",
                "排序后只需看日期频次和连续块；其它形态总能被对手安排结果避开所有预测。",
            ],
            "solution_brief": "关键观察：把每天登机方式编码成 0/1。必胜结构只有两类：同一天 4 个赌约覆盖四种二日结果；或者某个连续日期段两端都有至少两个赌约，中间不断档，可用固定预测保证序列中必出现被命中的相邻二元组。排序统计频次后检查这两类结构即可。",
            "primary_topic": "构造与贪心",
        },
        "2039H1": {
            "statement_brief": "给数组 a。一次操作是在 n×n 网格从左上走到右下，只能右/下移动；每经过 (i,j) 就交换 a_i 和 a_j。要求用不超过 2n+4 次这样的路径把数组排序。",
            "transformed_statement": "把题目先看成：精心设计的路径可以模拟相邻交换或长度 3 的局部翻转，从而在数组上实现一轮受限的奇偶排序。",
            "key_observations": [
                "路径经过对角线附近的两步形状，可交换相邻两项；经过三列形状，可把三项反转。",
                "先用一条路径把最小值放到 a_1，之后在 a_2..a_n 上反复做奇偶排序轮。",
                "每轮结束后用固定路径把最小值搬回头部，同时对子数组产生循环位移；根据长度奇偶调整比较起点即可。",
            ],
            "solution_brief": "关键观察：路径操作看似二维，本质是在数组上做特定相邻交换。构造几种固定路径作为“比较交换器”，先把最小值放到首位当锚点，再对剩余部分执行奇偶排序；每轮用一条横后竖路径恢复锚点并处理循环位移。总共 O(n) 条路径，简单版满足 2n+4 限制。",
            "primary_topic": "构造与贪心",
        },
        "2032C": {
            "statement_brief": "每次可把一个数组元素改成另一个已有元素。求最少操作数，使数组中任意三个不同下标的数都能组成非退化三角形。",
            "transformed_statement": "把题目先看成：排序后，只要最小两个数之和大于最大数，就能保证所有三元组都是合法三角形。",
            "key_observations": [
                "排序后最难满足的是最小两项和最大项；它成立则任意三元组都成立。",
                "保留一段连续区间 [i,j]，把区间外元素改成区间内值，就能维持最小、次小、最大来自这段。",
                "对每个 i，用双指针找最大 j 满足 a_i+a_{i+1}>a_j，答案为 n-(j-i+1)。",
            ],
            "solution_brief": "关键观察：所有三角形约束压成排序数组的一条不等式：a_1+a_2>a_n。最优等价于保留尽量长的连续值域段，使这段的最小两项和大于最大项；区间外都能改成区间内的数。排序后双指针维护最大合法段，最少操作就是 n-最长段长。",
            "primary_topic": "构造与贪心",
        },
        "2027A": {
            "statement_brief": "给若干不能旋转的矩形印章，每个都要在无限网格上盖一次，可重叠。求所有黑色连通区域周长之和的最小值。",
            "transformed_statement": "把题目先看成：把所有印章左下角对齐，所有黑格会落在最大宽和最大高形成的外接矩形内，周长只由这两个最大值决定。",
            "key_observations": [
                "为了最小周长，应尽量让印章重叠，而不是拆成多个连通块。",
                "任何方案的总外轮廓宽度至少是最大印章宽，高度至少是最大印章高。",
                "把所有印章同角对齐可同时达到这两个下界，答案为 2(max_w+max_h)。",
            ],
            "solution_brief": "关键观察：周长下界来自最大宽和最大高，无法通过摆放降低。把所有矩形的同一个角对齐，黑色区域外轮廓被最大宽和最大高撑起，并且只有一个连通区域，正好达到下界，所以答案是 2·(最大宽+最大高)。",
            "primary_topic": "几何",
        },
        "2207C": {
            "statement_brief": "有 n 列高度为 h 的水土网格，第 i 列底部 a_i 格是土，上方是水。最多放两个排水口，水可向下/左右连通到排水口则被排走，求最多排水格数。",
            "transformed_statement": "把题目先看成：一个排水口 i 能排走第 x 列中高度高于区间 [x,i] 最大土高的水；两个排水口的重叠部分等价于区间最高列的单排水量。",
            "key_observations": [
                "单个排水口 i 的贡献可向左右扫，维护路径上的最大 a 值并累加 h-max。",
                "两个排水口 i<j 的贡献是 cnt_i+cnt_j 减去被重复计算的水。",
                "重复部分恰好等于 [i,j] 中最高土列 k 作为排水口的 cnt_k，因此枚举 j 时维护区间最大位置即可。",
            ],
            "solution_brief": "关键观察：重叠计算有漂亮化简。先 O(n^2) 求每个单排水口 cnt_i；对两个口 i,j，能同时流到二者的水，正好是放在区间最高土列 k 时能排掉的水，所以贡献为 cnt_i+cnt_j-cnt_k。固定 i 向右枚举 j 并维护 k，取最大值。",
            "primary_topic": "动态规划与状态设计",
        },
        "2165C": {
            "statement_brief": "给数组 a。每次花 1 枚硬币可让某个 a_i 加 1；每个询问给目标异或 c，求最少加多少后，存在 0≤b_i≤a_i 且所有 b_i 异或为 c。",
            "transformed_statement": "把题目先看成：从高位到低位看，a 中每一位可提供的 1 的数量序列，必须按字典序不小于 c 的二进制位序列。",
            "key_observations": [
                "若某个高位已有可用 1 多于 c 的该位需求，低位异或都能通过选择 b_i 调整。",
                "若高位一路相等而某位 c=1 但所有 a_i 该位都为 0，则当前 a 不可行。",
                "修复时从高到低处理缺失位，只需把一个元素加到该位变 1；实际会用到的候选元素只有最大的 O(log V) 个。",
            ],
            "solution_brief": "关键观察：可选 b_i≤a_i 的异或能力由高位资源决定。把每一位上 a_i 中的 1 的数量组成序列，与 c 的二进制从高到低比较；前者字典序不小于后者就可行。若某位不足，就选一个元素加到该位为 1，继续往低位处理。排序后只需保留最大的三十几个元素，每个询问模拟这些候选即可。",
            "primary_topic": "数据结构",
        },
        "2159B": {
            "statement_brief": "给 0/1 网格。矩形要求四个角都是 1 且高、宽都至少 2；对每个格子，求覆盖它的合法矩形的最小面积。",
            "transformed_statement": "把题目先看成：对每一对上下边界行，只需要相邻的可用列形成的最小矩形；这些极小矩形足以覆盖所有最优答案。",
            "key_observations": [
                "固定两行 u,d，能作为左右边界的列必须在这两行都是 1。",
                "同一对行中，只需枚举这些列的相邻对；更宽的矩形若覆盖某格，总能被某个更窄相邻对替代得不更差。",
                "把所有极小矩形的面积向内部格子传播，可按列做区间 DP；若行多列少不合适就转置网格。",
            ],
            "solution_brief": "关键观察：不用枚举所有左右边界。固定上、下两行后，所有共同为 1 的列按顺序排列，只取相邻两列形成的矩形，就构成足够的极小集合；任何最优覆盖都能在这个集合中找到。随后对每列维护行区间最小面积，并用区间包含关系把答案向内传播。",
            "primary_topic": "数据结构",
        },
        "2122B": {
            "statement_brief": "有 n 堆二进制元素，每堆初始为若干 0 在上、若干 1 在下，目标也是这种形式。一次操作可取任意堆顶元素插到任意堆任意位置；保证可达，求最少操作。",
            "transformed_statement": "把题目先看成：只需要数每堆必须从顶部拿走多少元素；凡是拿走的元素都能一次放到最终不会再动的位置。",
            "key_observations": [
                "若某堆 1 的数量要减少，必须先移走它上方所有 0，再移走多余的 1，共 a_i+b_i-d_i 次。",
                "否则若 0 的数量要减少，只需移走多余顶部 0，共 a_i-c_i 次。",
                "这些下界可同时达到：移出的 1 放到缺 1 的堆底部，移出的 0 放到缺 0 的堆上方合适位置。",
            ],
            "solution_brief": "关键观察：每次操作唯一必要成本是“从当前堆顶拿走一个必须离开本堆的元素”。如果 1 过多，必须先掀开所有 0 才能拿到底部多余 1；否则只需拿走多余 0。把各堆这个必要次数求和就是下界，而所有被拿出的元素都能直接放进某个最终位置，因此下界可达。",
            "primary_topic": "构造与贪心",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2053E": {
            "statement_brief": "树上一条毛毛虫由头 p、尾 q 定义，占据 p 到 q 的简单路径。两人轮流把自己一端向未占据邻点扩展，无法走则按规则可能胜、负或平；统计使 Aron 获胜的有序点对。",
            "transformed_statement": "把题目先看成：若某人能获胜，胜负只会在前两轮决定；之后对手总能撤回上一手，把局面拖回去。",
            "key_observations": [
                "若第 k 轮不能赢却第 k+2 轮能赢，对手可以反向撤销上一次扩展，矛盾。",
                "因此只需判断初始两端是否为叶子、是否邻接叶子，以及头尾路径上尾侧下一点的性质。",
                "计数时先统计 q 是叶、p 非叶的基本贡献，再枚举靠近 q 的关键点 m 统计第二轮获胜贡献。",
            ],
            "solution_brief": "关键观察：游戏不会拖很久才分出真正胜负。因为对手总能撤回上一手，所有必胜都压到前两轮：q 是叶且 p 不是叶时 Aron 立刻有利；若两端都非叶，则 Aron 第二轮赢当且仅当 p 不邻接叶子，而从 p 往 q 走的下一点邻接叶子。把叶子数、非叶邻居数预处理后线性计数。",
            "primary_topic": "树结构",
        },
        "2252A": {
            "statement_brief": "有 n 张伤害牌，可任意重排。若连续打出两张相同伤害，护盾从下一张开始使后续伤害为 0，但触发那张仍造成伤害；求最优可造成的最大总伤害。",
            "transformed_statement": "把题目先看成：只有出现次数最多的伤害值可能被迫相邻，其它牌都应作为隔板尽量延后触发护盾。",
            "key_observations": [
                "所有非众数牌都可以安全打出，并用来隔开众数牌。",
                "若众数出现 F 次，其它牌 O 张，最多可安全穿插 O+1 张众数，再额外打一张众数作为最后的触发牌。",
                "因此众数最多贡献 min(F,O+2) 张，其它牌全部贡献。",
            ],
            "solution_brief": "关键观察：触发护盾的那张牌仍有伤害，所以应把第一次相邻相同安排在最后。取出现次数最多的伤害 X，用所有其它牌作隔板，可放 O+1 张 X 不触发，再在末尾多放一张 X 触发。答案是其它牌总和加 X·min(F,O+2)。",
            "primary_topic": "构造与贪心",
        },
        "2238F": {
            "statement_brief": "无限大的完全二叉员工树每天先扩展一层下属，再可开除一个员工及其子树；给 n 和 k，统计 n 天后恰好剩 k 个工作员工的最优开除次数方案数。",
            "transformed_statement": "把题目先看成：每个被开除的叶子位置最终会展开成一棵完整二叉子树，剩余节点数可表示为若干个 2 的幂之和减 1。",
            "key_observations": [
                "第 t 天开除的叶子，到结束时相当于贡献大小 2^{n-t+1} 的叶子块。",
                "最少开除次数等价于用尽量少的、指数小于 n 的 2 的幂表示 k+1。",
                "块数确定后，树形数量是卡特兰数，给叶子分配各类幂的数量再乘多重排列数。",
            ],
            "solution_brief": "关键观察：把动态雇佣/开除过程反向看成最终二叉树的叶子展开。若有 m 个被开除叶子，剩余点数满足 k+1=Σ2^{c_i}；所以先把 k+1 的二进制中超过高度限制的高位不断拆成两个低位，得到最少叶子数。方案数=对应叶数的二叉树形数×各高度标签的多重排列数。",
            "primary_topic": "组合计数与概率",
        },
        "2217A": {
            "statement_brief": "数组游戏中两人轮流把某个正数减一，最后行动者胜。先手至多一次可把整个数组改成全 k，判断先手是否必胜。",
            "transformed_statement": "把题目先看成：普通游戏只看总和奇偶；特殊操作如果要用，最好第一步就用，因为它只会把之后游戏变成总和 n·k 的普通游戏。",
            "key_observations": [
                "不使用特殊操作时，游戏总步数等于 sum(a)，奇数则先手胜。",
                "若 sum(a) 为偶，先手必须第一步使用特殊操作，之后轮到后手面对总和 n·k 的普通游戏。",
                "后手在普通游戏中面对偶数总和会输，因此先手胜当且仅当 sum(a) 为奇或 n·k 为偶。",
            ],
            "solution_brief": "关键观察：所有操作都只改变总步数奇偶。普通玩法下答案是 sum(a) 的奇偶；特殊操作若不是第一步用，只会少一次普通减一，没有额外信息，所以只需考虑第一步重置成全 k。于是判断 sum(a) 是否奇，或 n·k 是否偶。",
            "primary_topic": "博弈",
        },
        "2211E": {
            "statement_brief": "交互式给一棵根树，每个点有权值；好竖直路径要求路径上权值 gcd 不为 1。对每个后缀子树 S(u)，在线输出覆盖所有点的最少好路径数。",
            "transformed_statement": "把题目先看成：每个点向父亲最多延伸一条未闭合路径；不必保存所有 gcd 状态，只需保存这些可向上路径 gcd 的最小公倍数。",
            "key_observations": [
                "把“每点恰好覆盖一次”放宽成“至少覆盖一次”不会改变最优值，因为多覆盖路径可局部裁掉。",
                "每个子节点最多有一条路径继续向上，所以父节点只要知道哪些路径还能和 a_x 保持 gcd>1。",
                "所有可能向上 gcd 的集合可用它们的最小公倍数等价表示；若合并后为 1，则必须在当前点新开一条路径。",
            ],
            "solution_brief": "关键观察：别对每个节点存所有因子，权值太大不可分解。由于一棵树中每个点只有一个父亲，向上的未闭合路径每个儿子最多一条；这些路径能否继续与当前点合并，只由它们 gcd 候选集合的最小公倍数是否还含公共质因子决定。维护 dp(x) 和 val(x)，合并儿子 val 的最小公倍数，若变成 1 就新增一条路径并把 val 设为 a_x。",
            "primary_topic": "树结构",
        },
        "2210E": {
            "statement_brief": "交互题：隐藏二进制串 s。询问区间 [l,r] 会得到该子串所有循环移位逆序数对长度取模后的不同值数量；要求用有限成本确定 s，可猜两次。",
            "transformed_statement": "把题目先看成：长度 m 子串的回答只等于 m/gcd(m, 其中 1 的数量)，所以偶数长度询问能告诉你该区间 1 的个数奇偶。",
            "key_observations": [
                "循环左移时，逆序数对模 m 每次都增加子串中 1 的数量，因此不同值数为 m/gcd(m,cnt1)。",
                "当 m 为偶数时，回答能区分 cnt1 的奇偶。",
                "原串和取反串的所有回答相同，所以先假设首位，再用长偶数前缀/后缀询问恢复相邻字符异或，最后提交原串和取反串。",
            ],
            "solution_brief": "关键观察：询问值不是神秘函数，它只取决于区间内 1 的个数和区间长度的 gcd。用偶长区间可以得到 1 的奇偶；为了把总成本压到 3n 内，每个相邻关系选择更长的偶前缀或偶后缀来问，恢复相邻异或。由于整体取反不可区分，构造一个候选串后再猜它的取反。",
            "primary_topic": "交互",
        },
        "2061I": {
            "statement_brief": "n 场比赛中，付费场可花 a_i 保证 Kevin 赢，否则输；历史场由当前双方胜场多少决定。要求对每个 k，求保证至少赢 k 场的最小花费。",
            "transformed_statement": "把题目先看成：基础 DP 是前 i 场赢 j 场的最小花费；难点是批量跨过一段比赛时，胜负差足够大后历史场结果会固定。",
            "key_observations": [
                "若进入区间时胜场差大于区间长度，区间内所有历史场都会自动赢；若小于负区间长度，则都会输。",
                "在这种稳定区间里，只需从付费场中选若干个最便宜的买胜，选择代价函数是凸的。",
                "凸转移的最优断点单调，可用分治优化；中间不稳定区域继续递归拆分处理。",
            ],
            "solution_brief": "关键观察：直接 dp(i,j) 是 O(n^2)，而且不容易优化；要按区间转移。进入某段时如果胜负差绝对值超过段长，历史场结果已经被锁死，剩下只是从付费场里选若干个最小代价，形成凸函数，可用单调性分治。对未锁死的中间带递归分裂，整体得到近似分治 DP 的 O(n log^2 n) 级做法。",
            "primary_topic": "动态规划与状态设计",
        },
        "2027D2": {
            "statement_brief": "给数组 a 和递减数组 b。可免费把 k 加一，或花 m-k 删除一个和不超过 b_k 的非空前缀；困难版要求最小总代价及达到最优的操作序列数。",
            "transformed_statement": "把题目先看成：D1 的最短代价 DP 之外，还要把一次删除前缀对一段终点的贡献做区间加，而不是逐点转移。",
            "key_observations": [
                "预处理 nxt[i][k]：从 i 开始在限制 b_k 下最多能删到哪里。",
                "计数时一个状态会转移到同一 k 下的一段终点，朴素枚举会超时。",
                "按固定 k 从左到右扫描，用差分事件维护当前覆盖到的最小代价及方案数；也可利用单调性去掉对数。",
            ],
            "solution_brief": "关键观察：困难版卡在“有多少条最优序列”。对每个 k 预处理每个起点能删除的最远右端；一个 dp 状态会给一整段终点相同代价贡献，因此用区间事件加/删维护当前可达状态集合。扫描 i 时取集合中最小代价及方案数作为 dp，再发出免费升 k 和删除前缀两类区间更新。",
            "primary_topic": "动态规划与状态设计",
        },
        "2249F": {
            "statement_brief": "给无向简单图，要求找从 1 到 n 的最短偶长度简单路径，若不存在则输出 -1。",
            "transformed_statement": "把题目先看成：简单路径的度数模式可以编码成一般图完美匹配；端点度为 1，内部使用点度为 2，未使用点度为 0。",
            "key_observations": [
                "把每个点拆成左右副本，删除 R(1) 和 L(n)，让端点天然只接一条路径边。",
                "原图边在同层连接，未使用的内部点用左右副本之间的边匹配掉。",
                "同层边权设为 M-1，内部不使用边权设为 M；最大权完美匹配会先保证结构，再最小化路径长度并消除多余环。",
            ],
            "solution_brief": "关键观察：普通最短路管不了“简单且偶长”。把路径的度数约束转成匹配：内部点若不用就匹配自己的左右副本，若使用就两边都接原图边；删除两个端点副本强制从 1 到 n。偶长由删除的副本分属不同层保证。求最大权完美匹配后，从匹配边还原最短偶简单路径。",
            "primary_topic": "图论与网络流",
        },
        "2237H": {
            "statement_brief": "树上有一个始终连通的黏液占据 m 个点。给食物序列，黏液可移动一个占据点保持连通，吃到当前食物后下一个才出现；询问多段食物序列的最少移动次数。",
            "transformed_statement": "把题目先看成：给黏液指定一个核心点，每次食物只是把核心移到目标；目标若可能仍在黏液内部则免费，否则花一次移动。",
            "key_observations": [
                "不需要立即决定移走哪个黏液点，可以懒惰地给可能占据区域打标记，并记录每个标记还剩多少真实点。",
                "任一点拥有的标记集合总是时间后缀，因此可把剩余容量做后缀最小化。",
                "访问目标点时，找最早还能消耗容量的标记；若找不到才付费移动一个点过来。",
            ],
            "solution_brief": "关键观察：核心点可以贪心直接走到下一个食物，真正困难是“目标点是否仍可能被黏液覆盖”。移动时先不删具体点，只留下候选标记和容量；由于树上连通候选对每个点形成时间后缀，容量可转成差分并用集合/重链维护。能消耗容量就免费吃，否则答案加一并重置该点标记。",
            "primary_topic": "数据结构",
        },
        "2229H": {
            "statement_brief": "含 0/1/? 的字符串先把问号任意替换，再可反复删除 1 的个数为偶数的子串；求最终可能得到多少种不同二进制串。",
            "transformed_statement": "把题目先看成：目标串 t 能否从 s 保留下来，等价于按顺序匹配 t，且相邻保留字符之间被删掉的部分都含偶数个 1。",
            "key_observations": [
                "没有问号时，贪心取每个字符的最早可行匹配是正确的。",
                "有问号时，问号取值会影响当前后缀 1 的奇偶，所以必须同时维护最早偶奇两种匹配位置。",
                "计数时把贪心状态写成一对位置，预处理每个位置之后最早偶/奇匹配，转移只需尝试追加 0 或 1。",
            ],
            "solution_brief": "关键观察：删除偶 1 子串后，剩下的串就是一个子序列，且每两个保留字符之间的删除段 1 的个数为偶数。无问号时最早匹配贪心可证；有问号时同时保留“当前后缀奇偶为 0/1 的最早位置”。于是对贪心状态做 O(n^2) 动态规划，追加一个字符时用预处理的最早匹配表 O(1) 转移。",
            "primary_topic": "字符串",
        },
        "2155B": {
            "statement_brief": "构造 n×n 方向网格，使恰好 k 个起点沿箭头最终走出网格，其余起点会陷入循环；若无解输出 No。",
            "transformed_statement": "把题目先看成：除 k=n²-1 外都可构造；想困住一个格子不可能只困住它自己，因为它的箭头要么出界要么指向另一个也不会逃的格子。",
            "key_observations": [
                "k=n²-1 意味着恰好 1 个格子不逃，但单个不逃格无法自洽形成循环。",
                "其它 k 可先填 k 个向上的格子，它们会一路向上出界。",
                "剩余格子向下走到最后一行，再由最后一行左右箭头形成二元环或更长陷阱。",
            ],
            "solution_brief": "关键观察：唯一无解是只留下一个不能逃的起点，因为逃逸/不逃逸状态沿箭头传递，单点无法形成封闭环。构造时从左到右、从上到下放 k 个 U 作为逃逸区；其它非末行放 D，把人送到最后一行；末行用 R/L 做封闭横向循环，保证剩余起点都逃不出去。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2151C": {
            "statement_brief": "给出博物馆门口的 2n 个通过时刻，但不知道每次是进还是出，也不知道是谁。对每个容量 k，求在同时最多 k 人在馆内时，总停留时间的最大值。",
            "transformed_statement": "把题目先看成：在任意两个相邻事件之间，贡献等于当前馆内人数乘以时间差；所以固定 k 时，要让每段馆内人数在合法奇偶下尽量大。",
            "key_observations": [
                "前 k 个事件一定都应视为进入，后 k 个事件一定都应视为离开，否则会浪费容量或无法清空。",
                "中间事件后的人数奇偶由事件序号决定，因此人数最多只能取 k 或 k-1。",
                "总贡献可拆成首段、尾段和中间奇偶段三部分，分别用前缀和快速计算。",
            ],
            "solution_brief": "关键观察：固定容量 k 后，最优策略不是匹配具体游客，而是让馆内人数尽量贴着上限。前 k 次全进、后 k 次全出；中间每次若人数已到 k 就出，否则进，使人数始终是满足奇偶的最大值。把这些系数乘到对应时刻上，用若干前缀和即可算出所有 k。",
            "primary_topic": "构造与贪心",
        },
        "2127D": {
            "statement_brief": "给无向连通图，要求把房子放在河两岸两条平行直线上，所有边跨岸且画成直线后不相交，统计合法摆放方案数。",
            "transformed_statement": "把题目先看成：可画成无交叉跨岸桥的连通图结构极窄；删掉所有叶子后，剩余核心必须是一条简单路径。",
            "key_observations": [
                "任何环都不可能合法摆放，因为取一侧最靠左的点会强迫边交叉。",
                "如果某个点连接三个以上非叶方向，也会出现不可避免的交叉子结构。",
                "删叶后的核心为空、单点或路径时分别计数；叶子只需围绕父点在两侧排列。",
            ],
            "solution_brief": "关键观察：先判结构，不要直接数排列。合法图必定是一棵树；进一步，所有非叶节点形成的核心只能是一条路径。路径核心的左右方向、两岸交换、路径顺序给出主体因子；挂在核心点上的叶子可以在父点附近两侧独立排列。若核心为空或只有一个点，则按星形特例计数。",
            "primary_topic": "树结构",
        },
        "2098A": {
            "statement_brief": "给一个已经满足第 i 位至少为 10-i 的十位美丽号码，允许重排数字，求字典序最小的美丽号码。",
            "transformed_statement": "把题目先看成：每一位都有一个最低门槛；从左到右放当前还能满足门槛的最小数字即可。",
            "key_observations": [
                "第 i 位门槛为 10-i，越往后限制越弱。",
                "原号码本身合法，所以在任意前缀用了若干数字后，当前位置总能找到可用数字。",
                "当前位置选更大的数字只会让整体变大，不会给后续带来必要好处。",
            ],
            "solution_brief": "关键观察：这个贪心不需要回溯。按位置从左到右，每次选剩余数字中不小于当前门槛的最小值；因为门槛单调降低且原串已经美丽，后面一定能补完。于是局部最小就是全局最小。",
            "primary_topic": "构造与贪心",
        },
        "2096D": {
            "statement_brief": "无限网格上最初只有藏宝灯亮；每次翻转一个斜着的四灯形状。给最终亮灯坐标，求一个可能的藏宝位置。",
            "transformed_statement": "把题目先看成：每次操作在某条竖线和某条斜对角线上的翻转数量都是偶数，因此只有藏宝所在的竖线和斜对角线保留奇偶异常。",
            "key_observations": [
                "一次操作会在 x=u 和 x=u+1 两条竖线上各翻转两个灯，所以每条竖线亮灯数奇偶不变，除藏宝竖线外都为偶。",
                "同理，按 x+y=c 的斜对角线看，每次操作也只会翻转偶数个灯。",
                "找到亮灯数为奇的竖线 s 和亮灯数为奇的斜线 d，藏宝点就是 (s,d-s)。",
            ],
            "solution_brief": "关键观察：不要还原操作序列，只追踪两个不变量。竖线亮灯数的奇偶能直接给出藏宝点横坐标；斜线 x+y 的奇偶能给出横纵坐标和。最终答案就是唯一奇竖线 s 与唯一奇斜线 d 的交点。",
            "primary_topic": "数论与同余",
        },
        "2064B": {
            "statement_brief": "数组分数定义为长度减不同元素个数。最多删除一个非空连续子数组，要求分数最大；若分数相同，最终数组越短越好。",
            "transformed_statement": "把题目先看成：删除元素不会让分数增加；要保持最优分数，只能删除那些全局只出现一次的元素。",
            "key_observations": [
                "删除一个元素会让长度减一，而不同元素数最多也只减一，所以分数绝不会上升。",
                "出现多次的元素删掉一个后，不同元素数不变，分数必然下降。",
                "只出现一次的元素删掉后，长度和不同元素数同时减一，分数不变；因此选最长连续唯一段。",
            ],
            "solution_brief": "关键观察：目标最大分数其实就是原分数，删除只用于平手时缩短数组。能无损删除的元素必须在全局只出现一次，所以扫描最长的全局唯一元素连续段；若没有这样的段，就不删除。",
            "primary_topic": "构造与贪心",
        },
        "2061H2": {
            "statement_brief": "图上若干石子每轮必须同时沿边移动，且任意时刻每点最多一颗石子。判断能否从初态变到目标态，困难版还要输出不超过 2n 步的方案。",
            "transformed_statement": "把题目先看成：同步移动只关心步数奇偶和连通分量内石子数量；把每个点拆成偶步、奇步两个状态后，二分图奇偶限制会自然出现。",
            "key_observations": [
                "初态和目标态都必须至少能做一次合法同步移动，这可用匹配判断。",
                "每个连通分量内石子数量必须相同；若分量是二分图，还要满足两侧数量随奇偶步交换的限制。",
                "用 (点,奇偶) 建分层图后，只需枚举最终奇偶，并在该框架里统一检查和构造。",
            ],
            "solution_brief": "关键观察：同步移动不是逐个石子找路，而是整体奇偶可达性问题。把点复制成偶层和奇层，原图边连接相反奇偶层；这样非二分分量会自动连通两个奇偶状态，二分分量则保留部集限制。再用匹配保证当前每颗石子都能同时移动，最后按构造过程输出短序列。",
            "primary_topic": "图论与网络流",
        },
        "2059E2": {
            "statement_brief": "有 n 个长度为 m 的数组，一次操作从某个数组开始向后级联插入并挤出尾元素。困难版要求输出把初态变成目标态的全部操作。",
            "transformed_statement": "把题目先看成：沿用简单版的归纳顺序，每次应找到最靠右且已经位于某个数组末尾、但后面仍需插入元素的位置。",
            "key_observations": [
                "简单版证明实际上给出了构造算法：按某个元素成为尾部的时刻反向恢复操作。",
                "对每个还没处理的元素，维护它还差多少次后缀插入才会成为所在数组尾部。",
                "插入一次后，对它右侧后缀的等待次数全部减一；处理完成的元素设成极大值避免再选。",
            ],
            "solution_brief": "关键观察：困难版不是重新想策略，而是把简单版归纳证明实现出来。线段树维护每个剩余元素的“距离成为尾部还差几次插入”，每次找最右的零位置作为下一步操作点；执行后对后缀减一，并把已完成位置封掉。这样操作顺序天然合法。",
            "primary_topic": "数据结构",
        },
        "2020D": {
            "statement_brief": "n 个点排成一行，每次操作连接一个公差 d≤10 的等差点列中相邻点。执行所有操作后，求连通块数量。",
            "transformed_statement": "把题目先看成：因为公差只有 10 种，可以对每个公差和每个同余类扫描覆盖区间，遇到连续被覆盖的位置就合并。",
            "key_observations": [
                "一次操作只是在固定公差 d、固定同余类上覆盖一段等差区间。",
                "扫描位置时维护当前有多少覆盖区间仍有效；若当前位置和前一个同余位置都在覆盖中，就应并查集合并。",
                "用开始计数和结束计数维护覆盖数量，不需要展开每条操作的所有边。",
            ],
            "solution_brief": "关键观察：小公差把问题从大量边变成 10 组线性扫描。对每个 d，把所有操作记成等差区间的起点和终点；扫描每个位置 j 时更新覆盖数，如果同余类前一个位置仍被覆盖，就把 j 和 j-d 合并。最后统计并查集根数。",
            "primary_topic": "图论与网络流",
        },
        "2257A": {
            "statement_brief": "初始有若干单词；每次可用已有单词首字母组成一个缩写，并把缩写也加入词集。给一批缩写，判断它们是否都可能生成。",
            "transformed_statement": "把题目先看成：新生成的缩写不会带来新的首字母能力，因为它的首字母本来就来自某个已有单词。",
            "key_observations": [
                "生成一个缩写只需要它的每个字符都能作为某个已有单词的首字母。",
                "缩写加入词集后，其首字母仍是原本可用的字母，不会扩张可用字母集合。",
                "因此只需记录初始词集中出现过哪些首字母，再检查所有缩写字符。",
            ],
            "solution_brief": "关键观察：闭包其实一步就稳定。新增缩写最多提供自己的首字母，而这个字母在生成它时已经可用；所以后续操作没有新增能力。记录 26 个可用首字母，所有缩写中每个字符都在集合内则可行，否则不可行。",
            "primary_topic": "字符串",
        },
        "2238D": {
            "statement_brief": "把 n 的所有大于 1 的约数分成若干层。真约数必须在更早层，同层约数要能排成相邻最大公约数大于 1 的链。求最少层数。",
            "transformed_statement": "把题目先看成：质因子总数给出向上的最长链，不同质因子又必须各自单独占用靠前层。",
            "key_observations": [
                "任意质因子 q 不能和其它数同层，否则同层链上相邻数会含 q，使 q 成为对方真约数而应在更早层。",
                "设 n 的质因子指数和为 A，不同质因子数为 m；至少有一个质因子排在第 m 层或之后。",
                "从该质因子一路乘质因子到 n，需要再严格上升 A-1 层，所以下界是 A+m-1；按质因子个数分层可达到。",
            ],
            "solution_brief": "关键观察：答案只由质因子分解决定。所有不同质因子必须放在互不相同的单点层；选其中最晚的质因子 r，从 r 到 n 每次多乘一个质因子都会因真约数条件强制进入更后层，得到 A+m-1 的下界。把所有 Ω(d)=l 的约数放同一层可以构造达到该下界。",
            "primary_topic": "数论与同余",
        },
        "2189B": {
            "statement_brief": "青蛙从 0 出发，有多种跳跃；第 i 种每次最多前进 a_i，但每第 b_i 次使用前会先回退 c_i。求到达 x 的最少回退次数，或判断不可达。",
            "transformed_statement": "把题目先看成：只要能第一次到达不小于 x，就能把最后一跳缩短到正好 x；所以每次都按最大距离跳不亏。",
            "key_observations": [
                "每种跳跃先有 b_i-1 次免费使用机会，全部用掉可先获得一段无回退前进。",
                "之后每经历一次回退，继续使用同一种跳跃 b_i 次，净推进为 a_i b_i-c_i。",
                "为了最少回退，之后永远选择净推进最大的跳跃；若最大净推进不正，则无法继续向前。",
            ],
            "solution_brief": "关键观察：回退次数是分阶段算的。先把所有类型的免费跳跃次数都用满，得到剩余距离 r；若 r≤0 答案为 0。之后每付出一次回退，最优是选择净收益最大的完整周期，净收益 m=max(a_i b_i-c_i)，答案为 ceil(r/m)，若 m≤0 则无解。",
            "primary_topic": "构造与贪心",
        },
        "2178H": {
            "statement_brief": "三种礼物初始各一个；可花对应价值新建一个，也可花 k 复制某一种礼物的全部数量。求让总价值变成 m 的倍数的最小花费。",
            "transformed_statement": "把题目先看成：只关心总价值模 m 的余数；三种类型独立做会遇到最小加法卷积，改成把所有操作统一放进同一张余数图。",
            "key_observations": [
                "单类型时，状态是当前余数；新建是 x→x+a，复制是 x→2x。",
                "三种类型分别求再合并会变成没有好结构的最小加法卷积。",
                "从空集合余数出发，把三种新建和全局翻倍都作为图边，最后减去初始三个礼物的成本校正。",
            ],
            "solution_brief": "关键观察：不要为三种礼物分别做余数动态规划再硬合并。把“当前总价值模 m”作为图上状态，新增任一礼物就是加 a、b、c，复制相当于对已有某类贡献翻倍；题解通过从空状态建图，把创建三种礼物也纳入操作，跑最短路得到最小额外成本，再扣回初始礼物已经存在的部分。",
            "primary_topic": "图论与网络流",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2165F": {
            "statement_brief": "给一个排列，统计有多少区间包含相对大小顺序为 2,1,4,3,5 的五元子序列。",
            "transformed_statement": "把题目先看成：对每个左端点只要求最小右端点；先固定前面的 2,1 部分，再找足够靠前且满足值约束的 4,3,5 部分。",
            "key_observations": [
                "固定左端点后，作为 1 的位置应取右侧第一个更小值，剩下只需接一个满足额外位置和值限制的三元结构。",
                "为最小化右端点，只需考虑在左端、右端和值最小三方面都不可被支配的三元结构。",
                "按 3 的值从大到小扫描时，每个 3 至多产生一个真正需要保留的候选，因此总候选数是线性的。",
            ],
            "solution_brief": "关键观察：不要枚举五元组。对每个左端点，前两位一旦确定，问题变成查询一个不可支配的 4,3,5 候选；题解证明最小候选中 5 必须是 3 右侧最近的更大元素，4 也随之固定。于是先用数据结构枚举所有线性数量的最小三元结构，再转成二维查询求每个左端点的最小右端点。",
            "primary_topic": "数据结构",
        },
        "2157B": {
            "statement_brief": "从原点黑格开始，字符 4 表示向四邻扩张一层，字符 8 表示向八邻扩张一层。问最终某个坐标是否变黑。",
            "transformed_statement": "把题目先看成：操作顺序不重要，只关心 4 的次数 a 和 8 的次数 b；八邻一步等价于横纵两个方向各推进一次。",
            "key_observations": [
                "对称后只需考虑 |x|,|y|。",
                "总横纵步数最多是 a+2b，因此必须有 |x|+|y|≤a+2b。",
                "同一方向最多被推进 a+b 次，因此还必须有 max(|x|,|y|)≤a+b；这两个条件也足够。",
            ],
            "solution_brief": "关键观察：把扩张区域看成可达点集。一次 4 提供一个横或纵单位，一次 8 可以同时提供一个横向和一个纵向单位。令 x,y 取绝对值，满足曼哈顿需求 x+y≤a+2b，且单方向需求 max(x,y)≤a+b，就一定能安排这些扩张让该格变黑。",
            "primary_topic": "几何",
        },
        "2133B": {
            "statement_brief": "有 n 个村民，每次选两人支付二者当前坏脾气较大值，使二者坏脾气都减少较小值并成为朋友。求让所有人连通的最小支付。",
            "transformed_statement": "把题目先看成：每个村民至少要参与一次付费操作；一旦每个人参与过，产生的零坏脾气村民可以免费把所有连通块接起来。",
            "key_observations": [
                "一次操作至少让其中一个人的坏脾气变成 0，之后零坏脾气之间连接不花钱。",
                "所以核心成本是用若干对覆盖所有村民，并最小化每对较大值之和。",
                "排序后最优是最大和次大配对、再把剩余最大和次大配对；若剩一个最小者，则再和已经归零的人配一次。",
            ],
            "solution_brief": "关键观察：连通性本身不是难点，覆盖每个人才是下界。排序后从大到小两两配对，每对成本等于较大的那个；若人数为奇，剩下最小者可和已归零的人再做一次，成本只是它自己。答案就是排序后从最大开始隔一个取一个的和。",
            "primary_topic": "构造与贪心",
        },
        "2124H": {
            "statement_brief": "定义好数组需要能由某个排列的区间最小值首次出现位置生成。给数组 a，求最长好子序列长度。",
            "transformed_statement": "把题目先看成：好子序列可以拆成若干段，每段以某个值 x 开头并在之后只允许使用不小于 x 的值，直到下一段开始。",
            "key_observations": [
                "题解先刻画好数组：若 b_i=x，要么 x=i，要么位置 x 本身也是 x，且从 x 到 i 的最小值不小于 x。",
                "这个条件让一个以 a_i 开头的完整段可以用区间动态规划表示。",
                "当遇到更大的 a_j 时，应尽早开始以 a_j 为根的新段；维护每个值最早可开启位置即可转移。",
            ],
            "solution_brief": "关键观察：先别直接在原数组上做最长子序列，而是把“好”的定义改写成段结构。设 dp(i,j) 表示以 a_i 作为段根、只看区间 i..j 中不小于 a_i 的数时能形成的最大长度；相等值可直接延长，小于根值跳过，大于根值则尝试从最早可开启的位置接一个新段。外层再用同样的最早开启数组扫一遍得到答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2257F1": {
            "statement_brief": "有一列平台，每个平台有长度和留在本平台跳跃的罚分；最大跳远距离 x≤5。支持修改平台，并询问从第 l 个平台起点到第 r 个平台终点的最小罚分。",
            "transformed_statement": "把题目先看成：由于 x 很小，一个区间只需要记录从区间起点后第 i 格出发、第一次落到区间右端外第 j 格的最小罚分。",
            "key_observations": [
                "单个平台的转移矩阵可直接由跳几次离开平台算出，最后一次跳出平台不产生罚分。",
                "相邻区间合并就是矩阵最小加法乘法：枚举第一次落入右区间的位置。",
                "线段树每个节点存 x×x 矩阵，修改重建叶子，询问合并区间矩阵后再处理最后一个平台。",
            ],
            "solution_brief": "关键观察：小跳距让连续平台可以压成常数大小矩阵。矩阵 c[i][j] 表示从区间左端偏移 i 出发，第一次跳到区间右边界外偏移 j 的最小罚分；两个区间拼接时枚举中间落点取最小值。这样区间查询和单点修改都变成线段树上的小矩阵合并。",
            "primary_topic": "数据结构",
        },
        "2229C2": {
            "statement_brief": "给非零整数数组。一次操作只能选当前为正的位置 i，并翻转前缀 1..i 的符号。要求在至多 n 次操作后最大化数组和，并输出操作位置。",
            "transformed_statement": "把题目先看成：若最大操作位置是 idx，那么最终数组形态几乎被 idx 唯一决定：idx 前全部取绝对值，idx 本身取负，idx 后保持原样。",
            "key_observations": [
                "从右往左处理可以把所有元素变成负数，这是简单版的构造。",
                "困难版中最大被操作位置 idx 不能被更右侧操作再次翻转，所以它初始必须为正，最终会变负。",
                "idx 左边总能通过简单版方法全部变正；因此只需枚举这个分界点，用前缀绝对值和后缀原和算最优。",
            ],
            "solution_brief": "关键观察：所有可能的最优结果只有 n+1 种。若不操作就保持原数组；否则设最右一次操作在 idx，则 idx 右侧不变，idx 被翻成负，idx 左侧可以通过从右往左的策略全部变正。预处理前缀绝对值和、后缀原和，枚举初始为正的 idx 选最大收益，再按简单版构造输出操作序列。",
            "primary_topic": "构造与贪心",
        },
        "2194F2": {
            "statement_brief": "给一棵带点权树和集合 B，统计删边集合，使每个连通块点权异或和都属于 B。",
            "transformed_statement": "把题目先看成：树形动态规划的状态是“当前子树中已切掉部分的异或值”；这些值只会落在 B 张成的异或线性空间里。",
            "key_observations": [
                "子树合并需要做异或卷积；若直接在 2^30 空间上做完全不可行。",
                "先取 B 的线性基，把所有可能状态压到 k 维空间。",
                "困难版继续把动态规划数组存成沃尔什-阿达马变换后的形式，儿子合并变成逐点相乘；切父边的修正项再按变换定义补回。",
            ],
            "solution_brief": "关键观察：状态空间不是所有 30 位整数，而是 B 的异或线性包。用线性基把状态压成 2^k 后，合并儿子就是异或卷积；困难版直接维护变换域数组，让卷积变成逐点乘法。处理“切掉当前子树并要求异或落入 B”时，只需计算若干指定点的和，并把它对变换域的影响按定义加回。",
            "primary_topic": "动态规划与状态设计",
        },
        "2176D": {
            "statement_brief": "给有向图和每个点的数值，统计长度至少为 2 的简单路径，使路径上的数列满足广义斐波那契递推。",
            "transformed_statement": "把题目先看成：以有向边 (u,v) 为开头的路径，下一步只能走到数值等于 a_u+a_v 的出邻点。",
            "key_observations": [
                "路径每延长一条边，新边两端数值和严格变大，因此按边两端和从大到小处理即可无环转移。",
                "设状态为从边 u→v 开始的合法路径数，转移到 v→w 时要求 a_w=a_u+a_v。",
                "对每个点维护按终点数值聚合的状态表，就能快速取出所有满足下一值的边贡献。",
            ],
            "solution_brief": "关键观察：虽然要求简单路径，但斐波那契数值递增保证不会在转移图里绕回。把每条有向边当状态，按 a_u+a_v 从大到小排序；处理 u→v 时，贡献是 1 加上所有从 v 出发、下一点数值为 a_u+a_v 的状态和。用每个点一张映射表按数值累加即可。",
            "primary_topic": "动态规划与状态设计",
        },
        "2164G": {
            "statement_brief": "交互题中隐藏一棵树。一次询问给一个点排列，返回每个前缀诱导子图的边数。要求非自适应地用不超过 31 次询问找出所有树边。",
            "transformed_statement": "把题目先看成：相邻前缀边数差能告诉当前点连向前面点的边数；通过多种排列分组，可以恢复每个叶子的父亲编号。",
            "key_observations": [
                "一个排列和它的反序可合起来得到每个点的度数。",
                "按三进制位把点分成三组，并循环排列三组，能得到每个点有多少邻居在该三进制位上不同。",
                "不断删除当前叶子时，叶子的父亲是唯一邻居；利用这些按位统计可恢复父亲编号，并同步更新父亲的度数和统计量。",
            ],
            "solution_brief": "关键观察：询问前缀边数的差分其实给出“当前点连向已出现点的边数”。先用排列和反序求所有度数，然后按三进制位分组做固定询问，得到每个点邻居在各位上的分布。拓扑删叶时，叶子只有一个邻居，所以这些位信息直接拼出父亲编号；删掉叶子后更新父亲继续剥树。",
            "primary_topic": "交互",
        },
        "2158E": {
            "statement_brief": "网格每格有高度。打洞后，若某格相邻已有汇点且自己高度不小于它，也会成为汇点。每次把某格高度降低，询问让全网格成为汇点的最少打洞数。",
            "transformed_statement": "把题目先看成：最少打洞数等于没有更低邻居的等高连通块数量；降高操作只会影响被修改格子附近的新旧连通块。",
            "key_observations": [
                "等高且相邻的格子可以合成一组；一组若没有严格更低的邻组，就必须自己打洞。",
                "每次降低某格时，为这个新高度创建一个新节点，并连到四邻当前节点和同格上一个节点。",
                "由于值只下降，重要性变化只发生在新节点及其邻接组，用并查集维护等高组并局部更新答案。",
            ],
            "solution_brief": "关键观察：汇点传播方向是从低到高，所以需要打洞的正是局部极小等高连通块。把每次修改后的格子版本当成新节点，和四邻最新版本、同格旧版本连边；相同高度合并成组。新版本只会让自己组变重要，或让更高邻组失去重要性，因此答案可以局部维护。",
            "primary_topic": "数据结构",
        },
        "2138F": {
            "statement_brief": "从初始线段 (0,0)-(1,0) 出发，每次以已有线段为底边补一个边长都在 [0.5,1] 内的三角形。要求在给定步数内构造目标整数点。",
            "transformed_statement": "把题目先看成：要同时从初始线段两端向目标点铺两条不相交的折线，最后一个三角形把两条折线合拢。",
            "key_observations": [
                "理论下界接近两条端点到目标点路径长度的上取整之和减一。",
                "当目标方向角合适时，重复堆叠同一个平行四边形单元即可沿直线推进。",
                "角度太小时，先构造一个 30 度辅助点，把问题转到边长仍合法、步数仍满足限制的平行四边形铺法。",
            ],
            "solution_brief": "关键观察：这题的构造不是随便画三角形，而是把每两次操作看成堆一个平行四边形单元。若目标方向在可控角度内，沿目标方向均分线段并重复复制单元即可；否则先用一个 30 度辅助三角形把夹角抬起来，再沿目标边平行推进。证明重点是所有边长保持在 [0.5,1]，且总单元数不超过允许上界。",
            "primary_topic": "几何",
        },
        "2136A": {
            "statement_brief": "一场足球赛分上下半场，每半场任一队都不能连续进三球。给半场比分和全场比分，判断是否可能。",
            "transformed_statement": "把题目先看成：上下半场互不影响；只需判断某一半场中比分 x:y 是否能由不出现三连同队进球的序列实现。",
            "key_observations": [
                "若一队进 x 球，另一队最多可以在开头、结尾和每两个球之间各塞最多两个球。",
                "因此大分不能超过小分的两倍再加二。",
                "上下半场分别套这个条件；第二半场比分是全场减去半场。",
            ],
            "solution_brief": "关键观察：单半场的可行性只有一个不等式。设较小进球数为 x，较大为 y；为了避免三连，较大一方最多在 x+1 个空隙里每个放两个球，所以 y≤2x+2。分别检查上半场 a:b 和下半场 c-a:d-b 即可。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2135B": {
            "statement_brief": "交互题：机器人在无限平面中，已知若干锚点但不知道自身初始坐标。每次沿上下左右移动后，评测返回当前位置到最近锚点的曼哈顿距离；要求少量询问还原初始坐标。",
            "transformed_statement": "把题目先看成：只要把机器人先移到足够远的角落，曼哈顿距离里的绝对值符号就固定了，返回值会变成 X+Y 或 X-Y 的线性表达式。",
            "key_observations": [
                "连续向同一方向移动 10^9 两次，可以保证当前位置在所有可能初始坐标和锚点的一侧。",
                "在远角落中，最近距离可写成锚点某个线性式的最小值或最大值减去当前坐标线性式。",
                "分别构造出 X+Y 和 X-Y 后，初始坐标可直接解出。",
            ],
            "solution_brief": "关键观察：交互返回的是最近曼哈顿距离，但把点推到足够远后，绝对值不再分情况。先移到一个远角，返回值结合所有锚点的 min(x_i-y_i) 可求出 X-Y；再移到另一个远角，结合 max(x_i+y_i) 求出 X+Y。两个线性方程解出初始坐标。",
            "primary_topic": "交互",
        },
        "2107E": {
            "statement_brief": "构造一棵 n 点根树，使所有点对的最近公共祖先深度之和与给定 k 的差不超过 1；无解则报告。",
            "transformed_statement": "把题目先看成：链形树权值最大，星形树权值最小；从链出发，把某些点往更浅祖先处重接，就能按三角数降低权值。",
            "key_observations": [
                "链形树最大权值为 C(n,3)，因为所有点对的公共祖先尽量深。",
                "把点 i 的父亲从 i-1 改到 a_i，会让权值减少 C(i-a_i,2)，但这些距离需要保持互异或为 1 才能不互相干扰。",
                "于是问题转成用互不相同的三角数把 C(n,3)-k 表示到误差 1 内，贪心取最大可用三角数即可。",
            ],
            "solution_brief": "关键观察：先从最大值的链开始做减法。移动一个靠后的节点到更浅处，减少量正好是一个三角数；为了让各次减少独立，重接距离按递减约束选择，等价于选不同三角数。题解证明从大到小贪心选三角数能覆盖所有可行目标，然后按这些选择输出父亲。",
            "primary_topic": "树结构",
        },
        "2092F": {
            "statement_brief": "二进制串的美丽值是相邻不同次数。对每个前缀，统计有多少个 k 能把它切成 k 段且每段美丽值相同。",
            "transformed_statement": "把题目先看成：原串只需压成连续相同字符块，并且每块只区分长度为 1 还是大于 1。",
            "key_observations": [
                "段的美丽值只和跨过多少块边界有关；长块允许在块内部切开，因此只需记录块类型 1 或 2。",
                "固定每段美丽值 m 和段数 k，能作为前缀终点的块下标会形成一个连续区间。",
                "从 k 段扩展到 k+1 段时，这个区间只会整体平移 m 或 m+1，取决于边界块能否被切开。",
            ],
            "solution_brief": "关键观察：不要在原字符串位置上做复杂切分。先压缩成块类型串：单字符块和长块。固定目标美丽值 m 后，每多切一段，合法前缀块编号集合始终是一个区间；长块可以把切点提前一格，短块不行。枚举 m，并维护这些区间，就能给每个前缀累加可行 k 数量。",
            "primary_topic": "字符串",
        },
        "2063C": {
            "statement_brief": "给一棵树，必须删除两个点及其 关联边，求剩余连通块数量最大值。",
            "transformed_statement": "把题目先看成：删除一个点会把连通块数增加当前度数减一；删除两个点的收益只由两点度数和以及是否相邻决定。",
            "key_observations": [
                "若删点 i,j 不相邻，答案贡献为 d_i+d_j-1。",
                "若二者相邻，先删一个会让另一个度数减一，贡献为 d_i+d_j-2。",
                "枚举第一个点后，临时降低邻居度数，再取当前最大度作为第二点即可。",
            ],
            "solution_brief": "关键观察：这题不是树形动态规划。删一个度为 d 的点，会把一个连通块拆成 d 个，净增加 d-1。枚举第一个删点，把它邻居的度数临时减一，然后从全局度数集合里取最大作为第二点；恢复后继续枚举，取最大值。",
            "primary_topic": "树结构",
        },
        "2055A": {
            "statement_brief": "两只青蛙在一排荷叶上轮流移动一格，不能停留也不能重合，无法行动者输。判断先手是否必胜。",
            "transformed_statement": "把题目先看成：两只青蛙之间距离的奇偶决定谁能一直逼近对方。",
            "key_observations": [
                "每回合两只青蛙都必须移动，所以它们位置差的奇偶会按回合固定交替。",
                "若起点同奇偶，先手回合时二者距离为偶且至少为 2，先手总能向对方逼近。",
                "若起点奇偶不同，同样策略会落到后手一方。",
            ],
            "solution_brief": "关键观察：不用搜索博弈树，只看 a 和 b 的奇偶。若两只青蛙起点同奇偶，先手每次都能朝后手走，把后手逼到端点无路可走；否则这个优势属于后手。答案就是判断 a,b 奇偶是否相同。",
            "primary_topic": "博弈",
        },
        "2053C": {
            "statement_brief": "递归观察区间 [l,r]：若长度小于 k 停止；否则取中点，奇长时把中点加入答案，再递归两侧。给 n,k 求最终答案和。",
            "transformed_statement": "把题目先看成：递归每一轮产生的所有区间长度相同且关于中心对称，只需逐轮维护区间数量和中点贡献。",
            "key_observations": [
                "第 i 轮所有待处理区间长度一致，因此总轮数只有 O(log n)。",
                "当长度为奇数时，同一轮所有中点成对关于 n+1 对称，贡献可用区间数量乘中心和计算。",
                "k 只是截断递归轮数：长度降到小于 k 后停止。",
            ],
            "solution_brief": "关键观察：不要真的递归所有段。每轮把所有同长区间一起处理；若当前长度为奇数，这一轮被加入的所有中点关于整体中心对称，贡献等于当前段数乘 (n+1)/2。随后长度折半、段数翻倍，直到长度小于 k。",
            "primary_topic": "构造与贪心",
        },
        "2046D": {
            "statement_brief": "有向图中每个点有若干信使，信使沿边移动并能复制计划。求初始最少给多少信使计划，才能让所有点被带计划的信使访问；无解则输出 -1。",
            "transformed_statement": "把题目先看成：先缩强连通分量；在有向无环图上，需要用若干条可相交路径覆盖所有分量，且每个起点可用路径数受初始信使数限制。",
            "key_observations": [
                "强连通分量内部任意点可互达，所以可以压成一个点并合并信使数量。",
                "可行性等价于存在路径分解，使每个点至少被一条路径经过，且从点 u 发出的路径数不超过 a_u。",
                "把每个点拆成入点和出点，强制入到出至少一单位流；再加费用表示需要在本点初始发放计划，最小费用最大流给出答案。",
            ],
            "solution_brief": "关键观察：复制计划后，问题不是最短路，而是“带计划的路径流覆盖”。缩点后建流网络：每个分量必须被至少一条流穿过，起点流量受该分量信使数限制；若最大流无法覆盖所有点则无解。为了最少初始计划，把从本点启动一条计划路径设为费用 1，其它转移免费，跑最小费用流。",
            "primary_topic": "图论与网络流",
        },
        "2046C": {
            "statement_brief": "给平面上的城市点，选择分割点 (x0,y0) 把点按四个象限分给四人，最大化四个象限中最少点数，并输出一个分割点。",
            "transformed_statement": "把题目先看成：扫描竖直分割线时，左半平面和右半平面各自需要找一段可行的水平分割线区间；两段有交就可行。",
            "key_observations": [
                "最优 x 只需在某个点的横坐标附近变化，因此扫描所有候选竖线即可。",
                "固定竖线后，左侧和右侧各自的问题都是：是否存在 y 使上下两边点数都至少为 k。",
                "每半边可行的 y 是一个连续区间；用维护纵坐标计数的数据结构快速求区间并判断交集。",
            ],
            "solution_brief": "关键观察：四象限公平性可以拆成两个半平面的同一个问题。按 x 扫描，把点从右集合移到左集合；对左右集合分别维护纵坐标计数，并求出能让上下两侧都至少 k 个点的 y 区间。若左右两个区间相交，就找到了分割点。直接维护最大可行值，也可配合二分。",
            "primary_topic": "数据结构",
        },
        "2021E3": {
            "statement_brief": "图中若干房子需要联网，可放至多 k 个服务器；房子到服务器的代价是路径上最大边权。对每个 k，求总延迟最小值。",
            "transformed_statement": "把题目先看成：最大边权路径代价适合用最小生成树式合并建重构树；在重构树上，给一个需要联网的叶子选祖先就代表它连到某个服务器的最大边权。",
            "key_observations": [
                "按边权从小到大合并连通块时，每次合并创建一个重构树新父节点，节点权值就是这条边权。",
                "固定服务器集合后，每个特殊叶子应选择最近的已保留祖先，总代价可转成重构树删边代价。",
                "从 k 到 k+1，最优方案可通过加入当前最长可用根到叶路径得到；贪心正确性来自答案序列的凸性。",
            ],
            "solution_brief": "关键观察：原图先变成重构树。边权最大值路径问题在重构树上就是祖先权值；放 k 个服务器等价于把重构树缩成 k 个叶子的保留树，并最大化被保留边权收益。每次增加一个服务器，只需加入当前还能贡献最多的路径，用堆维护最长可用路径，就能得到所有 k 的答案。",
            "primary_topic": "图论与网络流",
        },
        "2192F": {
            "statement_brief": "一排鱼中双方各选一条鱼轮流行动，能随机吃相邻且不大的鱼并增长；若轮到自己无法吃则会被邻居吃掉。求先手获胜概率。",
            "transformed_statement": "把题目先看成两阶段：双方鱼不相邻时各自在自己的扩张区间内独立随机成长；相邻后进入两条鱼正面对抗的小状态。",
            "key_observations": [
                "一条鱼独自扩张时，状态只需记录它已经吃掉的连续区间 [l,r] 和到达该区间的概率。",
                "若某条鱼在未相邻时无法继续吃，需要乘上另一条鱼仍存活且未相邻的概率才能计入胜负。",
                "当两条鱼相邻后，剩余过程由双方当前大小和左右剩余区间决定，可作为第二阶段动态规划处理。",
            ],
            "solution_brief": "关键观察：不要把双方行动混在一个巨大状态里。先分别计算每条鱼独立吞并左右连续区间的概率；轮次只由区间长度决定，因此能判断另一方此时是否还活着且未接触。等两条鱼的区间相邻后，再用第二阶段状态处理正面对抗概率，最后把两阶段贡献合并。",
            "primary_topic": "组合计数与概率",
        },
        "2187E": {
            "statement_brief": "一排房间和门，门会在指定时间自动开；部分房间有钥匙，一次最多携带一把钥匙，也可用钥匙提前开门。求最早到达终点。",
            "transformed_statement": "把题目先看成：最多带一把钥匙的限制可以改写为允许携带多把钥匙，但带 k 把穿过一条边需要来回搬运，耗时 max(1,2k-1)。",
            "key_observations": [
                "要把 k 把钥匙从一个房间整体搬到相邻房间，需要多次往返，等效耗时为 max(1,2k-1)。",
                "设 dp[i][j] 为到达房间 i 且携带 j 把钥匙的最早时间；遇到钥匙可选择拿或不拿。",
                "若门未自动打开，可用一把钥匙开门，或等到自动打开时间；携带钥匙数过大一定不优，因为门早已自动开。",
            ],
            "solution_brief": "关键观察：把“最多带一把”的来回搬钥匙过程压成边权。允许状态里带多把钥匙，过相邻门的成本按钥匙数计算；门已开就直接过，未开则二选一：消耗钥匙提前开，或等到 a_i。由于带 k 把至少要 O(k^2) 时间，钥匙维度只需做到 √max(a)。",
            "primary_topic": "动态规划与状态设计",
        },
        "2156F2": {
            "statement_brief": "给一个排列。一次操作可把某个值比后面两个相邻值级别高 1 和 2 的位置减 2，并把后面两个位置各加 1。求任意次操作后字典序最小排列。",
            "transformed_statement": "把题目先看成：第 t 轮要找到最靠左、能被降到 t 的存活元素，把它从当前排列中删除并写入答案位置。",
            "key_observations": [
                "一次操作除被降低的位置外，其它存活元素相对顺序不变，因此可模拟为删除一个元素并给答案赋值。",
                "当前元素能否被降到 t 只由它在存活值中的排名奇偶决定；奇排名可删，偶排名继续找右侧下一个更小元素。",
                "每个位置最多被访问两次：偶排名访问后，右侧删掉元素会让它下次变成奇排名。",
            ],
            "solution_brief": "关键观察：困难版的核心是把复杂操作改成“删元素填答案”。从 t=1 到 n，每轮找最靠左可删除元素；用值域树维护存活排名，若当前位置排名为奇就删除并赋 q_i=t，否则跳到右侧下一个更小的存活元素。访问总次数线性，树结构只负责排名、删除和找下一个更小值。",
            "primary_topic": "数据结构",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2155F": {
            "statement_brief": "树上每个点有一个颜色集合。每次询问一条路径，求有多少种颜色出现在路径上每个点的集合中。",
            "transformed_statement": "把题目先看成：对每种颜色，在包含该颜色的点诱导出的森林里划分连通块；一条路径上所有点都含某颜色，当且仅当路径两端落在同一个颜色连通块里。",
            "key_observations": [
                "把每个颜色连通块分配编号，点 u 所属的所有编号组成新集合 D_u，答案变成 |D_u∩D_v|。",
                "小集合询问直接双指针或哈希求交，大集合点则预处理它和所有点的交集答案。",
                "用总出现次数开方分界，在单次查询和整点预处理之间平衡复杂度。",
            ],
            "solution_brief": "关键观察：路径交集可以只看两端。若某颜色在整条 u-v 路径上都出现，那么 u 和 v 必在这个颜色的同一个连通块里；反过来也成立。于是先把“颜色连通块”当成元素，给每个点建立所属块编号集合，询问就是两点集合交大小。对小集合即时求交，对大集合点预处理全局答案。",
            "primary_topic": "数据结构",
        },
        "2152E": {
            "statement_brief": "交互题：隐藏排列长度为 n²+1，每次询问一组下标会返回其中从左到右看见的新最大值。要求在至多 n 次询问内找出长度 n+1 的单调子序列。",
            "transformed_statement": "把题目先看成：每次询问当前剩余下标，返回的一层可见点本身是递增子序列；如果每层都不够长，连续剥 n 层后就能从层号反向构造递减子序列。",
            "key_observations": [
                "若某次返回至少 n+1 个可见点，它们的值严格递增，直接作为答案。",
                "否则删除这一层可见点继续问；第 k 层正好对应最长递减子序列长度为 k 的点。",
                "经过 n 次还没找到递增答案时，剩余点非空，从最后一层往前选前驱即可得到长度 n+1 的递减子序列。",
            ],
            "solution_brief": "关键观察：询问返回的可见点不是废信息，而是在给排列做“递增层剥离”。每层可见点都是递增的；如果没有一层达到 n+1，那么第 k 层可视为递减动态规划值为 k 的点集。最后剩余点的递减长度至少 n+1，按层号从后往前找前驱，就构造出递减子序列。",
            "primary_topic": "交互",
        },
        "2152C": {
            "statement_brief": "给 0/1 数组，多次询问一个子数组能否反复删除三个相同值并清空；每次删除代价为中间间隔和两侧间隔的较小值，求最小总代价。",
            "transformed_statement": "把题目先看成：若 0 和 1 的数量不是 3 的倍数则无解；否则答案几乎总是长度三分之一，只有完全交替的子数组要多付一次代价。",
            "key_observations": [
                "每次删三个数，且每次代价至少 1，所以可行时下界是 len/3。",
                "只要子数组内存在相邻相同元素，就能安排每次以代价 1 删除，达到下界。",
                "没有相邻相同则子数组完全交替，需要先花代价 2 打破交替，之后再按代价 1 删除。",
            ],
            "solution_brief": "关键观察：复杂删除过程被相邻相同对控制。先用前缀和判断 0、1 数量是否都是 3 的倍数；再判断区间内是否存在相邻相同。存在则答案是区间长度/3；不存在说明完全交替，先用一次代价 2 的删除制造相邻相同，答案变成 2+(len-2)/3。",
            "primary_topic": "数据结构",
        },
        "2138B": {
            "statement_brief": "给排列，多次询问子数组是否“完美”：允许相邻交换和隔一位交换时，排序最少操作数是否仍等于只允许相邻交换的最少操作数。",
            "transformed_statement": "把题目先看成：隔一位交换只有在子数组中存在长度为 3 的下降子序列时才会真正省操作。",
            "key_observations": [
                "只允许相邻交换时，最少次数就是逆序对数。",
                "若存在 i<j<k 且 b_i>b_j>b_k，可以通过相邻交换把它们聚到一起，再用隔一位交换一次减少三个逆序。",
                "对每个中间点 j，找左侧最近的大值位置和右侧最近的小值位置；若对应区间被询问完全包含，则答案为不完美。",
            ],
            "solution_brief": "关键观察：判断是否省操作等价于判断是否有三元下降子序列。预处理每个位置作为中间点时，左侧最近大于它的位置 l_i、右侧最近小于它的位置 r_i；若某个 [l_i,r_i] 完全落在询问区间内，就存在可省一次操作的结构。再把每个左端能触发的最小右端预处理出来即可快速回答。",
            "primary_topic": "数据结构",
        },
        "2109B": {
            "statement_brief": "n×m 网格中怪物初始在 (a,b)。每回合先切掉不含怪物的一半网格，再由怪物任意移动到剩余格子。双方最优时求回合数。",
            "transformed_statement": "把题目先看成：第一次切之后，后续每轮可视为怪物先移动到最难切的位置，再切一维；行列维度可以独立计算。",
            "key_observations": [
                "后续把长度 l 的一维区间缩到 1，最坏情况下每次只能变成上取整的一半。",
                "第一次切可以利用已知初始位置，把行数变成 a 或 n-a+1，或把列数变成 b 或 m-b+1。",
                "枚举第一次切的四种剩余矩形，答案为 1 加上两维各自折半次数之和的最小值。",
            ],
            "solution_brief": "关键观察：首回合特殊，因为怪物位置还没来得及重选；之后它每轮都会站到最拖延的位置，所以每次只能把某一维近似减半。函数 f(l) 就是反复上取整折半到 1 的次数。枚举首刀保留上、下、左、右四种矩形，取 1+f(n')+f(m') 的最小值。",
            "primary_topic": "构造与贪心",
        },
        "2098B": {
            "statement_brief": "街上有若干酒吧，最多可关闭 k 个。一个房子可购买，当且仅当关闭某些酒吧后，它能成为到所有开放酒吧距离和最小的位置。求可购买房子数量。",
            "transformed_statement": "把题目先看成：距离和最小点就是中位数区间；关闭酒吧只会把可行中位数区间向内外两端调整。",
            "key_observations": [
                "一维绝对值和在中位数处最小；偶数个点时，两个中位数之间整段都最优。",
                "为了让某个位置成为中位数，最优关闭策略只会删排序后最左端或最右端的酒吧。",
                "排序后答案就是删掉至多 k 个端点后可能形成的最宽中位数区间长度。",
            ],
            "solution_brief": "关键观察：这题核心是中位数区间。把酒吧位置排序；关闭内部点不会比关闭两端更有利，因为中位数只受左右数量平衡影响。最多删 k 个后，可行购买位置从第 (n-k)/2 个附近延伸到第 (n+k)/2 个附近，按题解公式取对应排序位置差再加一。",
            "primary_topic": "数论与同余",
        },
        "2085A": {
            "statement_brief": "字符串若字典序小于自己的反转串则称为通用。给字符串和最多 k 次任意交换，判断能否变成通用。",
            "transformed_statement": "把题目先看成：如果已经小于反转串则成功；否则只要允许一次交换且字符串中有两种不同字符，就一定能成功。",
            "key_observations": [
                "所有字符相同则无论怎么换都不变，永远不能小于反转串。",
                "若当前串已经小于反转串，不需要操作。",
                "其余情况下，只要 k≥1 且存在不同字符，交换一对合适位置即可打破对称并让原串或其反转一方变小。",
            ],
            "solution_brief": "关键观察：任意交换能力很强，非全同字符串只需一次。先比较 s 和反转串；若 s 已更小直接可行。否则若 k=0 或所有字符相同则不可行；剩下情况一次交换就能把某个更小字符放到更靠前的镜像位置，使字符串变成通用。",
            "primary_topic": "构造与贪心",
        },
        "2078B": {
            "statement_brief": "有 n 个格子，每格一人；必须给每格设置一个不能指向自己的传送器，所有人恰好传送 k 次后，希望总距离出口的距离最小。",
            "transformed_statement": "把题目先看成：所有人不可能同时停在出口，因为函数图必有环且不能自环；最优总距离只能做到 1。",
            "key_observations": [
                "传送器形成函数图，每个人 k 次后落在某个环或入环路径上。",
                "没有自环，所以不可能让所有人最终都在出口 n，答案下界至少为 1。",
                "构造一个 n 与 n-1 的二元环，再按 k 的奇偶把其它点接到合适一侧，就能让只有一个人离出口一格。",
            ],
            "solution_brief": "关键观察：最优目标不是全到出口，而是除一个人外全到出口。令 n 和 n-1 互相传送形成二元环；若 k 为奇数，其它点直接指向 n，若 k 为偶数，其它点指向 n-1。这样 k 次后所有非例外点都在 n，剩下一个在 n-1，总距离为 1，且这是下界。",
            "primary_topic": "构造与贪心",
        },
        "2028A": {
            "statement_brief": "从原点按给定方向串循环移动，问是否会到达目标点。",
            "transformed_statement": "把题目先看成：一次完整方向串产生固定位移；目标若可达，一定等于某个前缀位置加上若干次完整位移。",
            "key_observations": [
                "枚举一个周期内所有前缀位置即可覆盖相位。",
                "若整周期位移为零，只需检查第一轮前缀。",
                "否则目标与某个前缀的差必须是整周期位移的非负整数倍；由于坐标很小，重复足够多轮模拟也能过。",
            ],
            "solution_brief": "关键观察：无限循环不用无限模拟。记录一轮内每个前缀坐标和整轮位移 (dx,dy)，检查是否存在前缀 (x_i,y_i) 与非负整数 t，使 x_i+t·dx=a 且 y_i+t·dy=b。数据小也可重复约 100 轮，题解证明这已经覆盖所有可能命中。",
            "primary_topic": "基础实现与模拟",
        },
        "2252F": {
            "statement_brief": "树上每个点有颜色。对每种颜色 c，要选一个大小为 k_c 的连通点集，使所有 c 色点到该点集的距离和最小。",
            "transformed_statement": "把题目先看成：固定一种颜色时，先找这些颜色点的树上中心；选择更大的连通块就是从中心向外吃掉若干条边来抵消距离贡献。",
            "key_observations": [
                "对一条边，所有目标颜色点到中心路径经过它的次数是两侧颜色点数较小值，记作这条边的收益。",
                "若选中的连通块包含中心，那么块内边的收益会从总距离中被减掉。",
                "收益沿离开中心的方向单调不增，所以取收益最大的 k-1 条边会自然形成连通块；多颜色用虚树压缩统计。",
            ],
            "solution_brief": "关键观察：固定颜色后，先把问题转成边收益。单点最优是这些颜色点的树上中心，总距离等于每条边被多少条到中心的路径经过之和；选 k 个点的连通块，相当于从中心出发加入 k-1 条边并扣掉这些边收益。由于收益向外单调下降，贪心取最大收益边即可；对每种颜色用虚树收集压缩路径上的相同收益段。",
            "primary_topic": "树结构",
        },
        "2246D": {
            "statement_brief": "数组游戏开始前先手可给元素加一若干次；之后后手每轮可交换任意两数，先手按首元素奇偶执行减一或整段除二。求先手最少总操作数。",
            "transformed_statement": "把题目先看成：后手会尽量把一个奇数放到第二位，让先手每次只能有效处理一个元素；只有全偶阶段能让先手整数组同时除二。",
            "key_observations": [
                "若数组里有奇数，后手可把奇数放到第二位，阻止前缀全偶扩展，之后先手基本逐个消数。",
                "若全是偶数，先手无论后手怎么换都能把全数组除以二，这是唯一的批量收益。",
                "枚举先手先把所有数补到 2^k 的倍数，前 k 轮全数组除二；每个数只需在附近少量候选倍数中找最省总成本。",
            ],
            "solution_brief": "关键观察：游戏分成“全偶批量除二”和“出现奇数后逐个处理”两段。枚举想保证的全偶轮数 k，把每个 a_i 增加到某个 2^k 的倍数；之后统一除 k 次，再按单个数的二进制消除成本计算。由于补太远不可能省回成本，只需检查最近少量倍数，取全局最小。",
            "primary_topic": "博弈",
        },
        "2234G": {
            "statement_brief": "一条带数值的格带上有令牌。每回合可先把令牌力量增加 0..a_i，再向前走不超过当前力量的正步数；落到终点者胜。判断先手胜负。",
            "transformed_statement": "把题目先看成：状态是当前位置和当前力量；虽然状态多，但败态很稀疏，可以只显式维护败态。",
            "key_observations": [
                "固定力量 k 时，两个败态位置之间至少相隔 k+1，因为败态后面 k 个位置都能一步走到它而成为胜态。",
                "因此所有败态总数只有 O(n log n) 量级。",
                "从右往左枚举位置 i，若一整段力量 k..k+a_i 都没有可到达败态，则 (i,k) 是败态；用连续区间容器维护这些力量段。",
            ],
            "solution_brief": "关键观察：不要做完整二维胜负表，只维护少数败态。对固定力量 k，败态位置很稀，因为它前面 k 个位置都能走到败态而获胜。倒序扫格子，维护哪些力量在可达范围内没有败态；若某个连续力量段 k..k+a_i 全满足，就得到新的败态 (i,k)。用区间集合和事件队列维护这些段，最后看初态 (1,1)。",
            "primary_topic": "博弈",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2229I": {
            "statement_brief": "给一棵带点权树和 k。对每个点 x 作为根，必须选 k 个点且包含 x，分数为所选点到根路径上的点权贡献总和，求最大分数。",
            "transformed_statement": "把题目先看成：根改变时，选点贡献可拆成“当前子树内”和“当前子树外”两部分；真正难点是把换根时的外部动态规划压到总平方复杂度。",
            "key_observations": [
                "先把路径到根的贡献改写成按子树累计，这样固定根时可做树上背包。",
                "dp1/dp2 处理子树内选点，dp3 处理子树外选点；答案由子树内外拼起来。",
                "对节点 i，外部 dp3 只需要关心能凑满 k 时的最大 sz(i) 个状态，不必保留整行。",
                "换根时用前后缀合并，或把高度节点拆成二叉结构，让所有合并成本摊到 O(n^2)。",
            ],
            "solution_brief": "关键观察：不要为每个根重做树背包。先在任意根下做子树内 dp；再换根计算每个孩子的“子树外”贡献。外部状态只保留与 k 相关的必要区间，配合前后缀或二叉化合并，使所有孩子拿到正确的外部背包，总复杂度为 O(n^2)。",
            "primary_topic": "树结构",
        },
        "2207D": {
            "statement_brief": "树上追逃游戏：Cyndaquil 想到叶子，Snorlax 每隔 k 步才能重新封一条边。给起点 v，判断 Cyndaquil 是否一定能逃到叶子。",
            "transformed_statement": "把题目先看成：Snorlax 想守住一个包含 v、内部没有叶子的连通区域；区域的不同出口之间必须足够远，才能来得及轮流封堵。",
            "key_observations": [
                "若存在两个出口距离小于 k，Cyndaquil 可以沿两出口之间来回压迫，最终逃出。",
                "叶子天然不能留在安全区域内，先全部标记为排除点。",
                "两个已排除分支距离太近时，它们之间的节点也必须被排除。",
                "自底向上维护到最近排除点的距离；若某点有两条子分支距离和足够小，就把该点也标记排除。",
            ],
            "solution_brief": "关键观察：问题不是模拟双方移动，而是判断起点是否会被“排除闭包”吞掉。以 v 为根，叶子先标记；令 dp[u] 为 u 到最近标记点距离。若两个子树标记点通过 u 的距离不超过限制，u 也必须标记。最后看起点是否被标记；标记表示不存在可长期困住 Cyndaquil 的安全区域。",
            "primary_topic": "树结构",
        },
        "2180A": {
            "statement_brief": "转盘有 l 个位置，从 a 出发，每次前进 b 格，可转任意次，求能停到的最大编号。",
            "transformed_statement": "把题目先看成：在模 l 意义下反复加 b，只会访问与 a 同余于 gcd(l,b) 的那些位置。",
            "key_observations": [
                "可达位置恰好满足 c≡a (mod gcd(l,b))。",
                "这个剩余类中小于 l 的最大位置是 l-gcd(l,b)+a%gcd(l,b)。",
                "数据小可模拟一圈，但 gcd 公式直接给 O(1) 解法。",
            ],
            "solution_brief": "关键观察：转盘运动是模 l 的等差循环。令 d=gcd(l,b)，可达集合就是 a 所在的模 d 剩余类；答案直接取该剩余类中最大的合法编号 l-d+a%d。",
            "primary_topic": "数论与同余",
        },
        "2166B": {
            "statement_brief": "屏幕上有 n 个标签页，剩余 m 个时每个标签长度为 min(b,a/m)，每次鼠标移到某个横坐标后可连续点击同一位置，求关完所有标签最少移动几次。",
            "transformed_statement": "把题目先看成：答案最多为 2；先在屏幕最右端点 a 关掉仍够长的标签，再移动到固定长度 b 的端点关完剩余标签。",
            "key_observations": [
                "在 a 处点击可以不断关闭所有仍覆盖到屏幕右端的标签。",
                "一旦右端没有标签，剩余标签长度都已经变成 b，移动到 b 就能一直点完。",
                "若一开始所有标签长度就是 b，或 b=a，那么只需移动一次到 b。",
            ],
            "solution_brief": "关键观察：不用模拟每个标签的位置变化。先证明两次移动总够：点 a，再点 b。能否一次完成只看最终要停在 b，而每个标签右端都必须曾经经过 b；条件为 n*b<=a 或 b=a，否则答案为 2。",
            "primary_topic": "基础实现与模拟",
        },
        "2155A": {
            "statement_brief": "n 支队伍打改造版双败赛，胜者组输一场掉到败者组，败者组再输淘汰，最后两组冠军打一场，求总比赛数。",
            "transformed_statement": "把题目先看成：每场胜者组比赛让一队掉入败者组，每场败者组比赛淘汰一队；只按人数变化计数即可。",
            "key_observations": [
                "胜者组最终只剩一队，所以必须有 n-1 队掉入败者组，也就是 n-1 场胜者组比赛。",
                "败者组最终在总决赛前只剩一队，而进入败者组的一共有 n-1 队，所以败者组淘汰 n-2 队。",
                "最后再加一场总决赛，总数为 (n-1)+(n-2)+1。",
            ],
            "solution_brief": "关键观察：轮次细节和轮空都不重要，只看每场比赛造成的人数变化。胜者组需要产生 n-1 个败者，败者组需要淘汰 n-2 个队伍，再加最后一场，因此答案恒为 2n-2。",
            "primary_topic": "基础实现与模拟",
        },
        "2153C": {
            "statement_brief": "给若干木棍，要求组成关于某条直线对称的非退化多边形，求最大周长；不能组成则输出 0。",
            "transformed_statement": "把题目先看成：对称多边形的大部分边必须成对出现，至多留下 0、1、2 条边落在对称轴上。",
            "key_observations": [
                "相同长度边优先两两配对，所有成对边都应尽量使用来增加周长。",
                "若没有未配对边，成对边本身可围成对称多边形。",
                "若有一条轴上边，必须满足最长轴边小于其它边长总和。",
                "若有两条轴上边，它们相邻时只需检查二者差值小于两倍配对边长总和。",
            ],
            "solution_brief": "关键观察：先按长度统计奇偶，把偶数份全部作为成对边。对称轴上最多承担两个未配对长度，因此只需讨论未配对长度数量。核心判定是非退化：一条轴边时检查它是否小于其余周长；两条轴边时检查差值是否能被配对边撑开。取能通过判定的最大周长。",
            "primary_topic": "几何",
        },
        "2127E": {
            "statement_brief": "树上部分点已有颜色或待定，每种颜色的点需要满足路径连通等约束；要求构造合法染色并最小化某类必须付费点权和。",
            "transformed_statement": "把题目先看成：每种颜色已确定点在树上生成一个虚树；若某个点被多个颜色虚树同时需要，它就是不可避免的付费点。",
            "key_observations": [
                "对每种颜色，把该颜色相关点按欧拉序建虚树，只需考虑这些路径上的关键点。",
                "出现在多个颜色虚树中的点无法只服务一种颜色，因此一定贡献代价。",
                "只出现在一种颜色虚树中的待定点可以安全染成那种颜色。",
                "剩余普通待定点按子树或父侧最近确定颜色补齐即可。",
            ],
            "solution_brief": "关键观察：不要逐个颜色在原树上扫路径，而是建颜色虚树。一个点若同时是多个颜色连通需求的关键节点，就无论怎么染都会成为冲突点，代价必付；其它虚树点染成对应唯一颜色。最后用树上遍历把非关键待定点补成相邻颜色，得到最小代价构造。",
            "primary_topic": "树结构",
        },
        "2120C": {
            "statement_brief": "构造一棵 n 个点的有根树，使所有点到根路径上的最小编号之和等于 m；无解则输出 -1。",
            "transformed_statement": "把题目先看成：每个点至少贡献 1，最多可通过把较大编号放到根路径前缀来增加贡献；总和范围是 [n,n(n+1)/2]。",
            "key_observations": [
                "可行性只需判断 n<=m<=n(n+1)/2。",
                "令 p=m-n，问题变成给若干点额外增加贡献。",
                "从大到小贪心选择增量 i，相当于把编号 i+1 放入一条从根开始的主链。",
                "未被选中的点接在 1 后面，贡献保持 1。",
            ],
            "solution_brief": "关键观察：把所有点的基础贡献 1 先扣掉。额外贡献 p 可由 0..n-1 这些增量贪心组成；选中增量 i 就把节点 i+1 放进主链，让它产生对应额外贡献。主链之后第一次接到 1，再把剩余点挂在 1 后，正好实现总和 m。",
            "primary_topic": "构造与贪心",
        },
        "2115F1": {
            "statement_brief": "维护 n 个集合的数组，在线执行前缀插入、前缀反转、全局删除某元素，并在每次操作后询问第 p 个集合的最小元素。",
            "transformed_statement": "把题目先看成：操作按时间分块；每一块内把当前集合数组切成少量连续段，段里懒记录本块插入的元素和反转状态。",
            "key_observations": [
                "前缀插入和前缀反转只会切割少量段，可在块内维护段队列和反转标记。",
                "删除元素不必立刻从所有段中删掉，只需打删除标记，查询时弹掉失效元素。",
                "每块结束后重建真实序列，把块内懒信息压回基础状态。",
                "块长取约 sqrt(q)，每次查询只需跨块检查少量段贡献。",
            ],
            "solution_brief": "关键观察：在线不代表每步都要真实维护所有集合。按操作分块，块内用 O(B) 个连续段表示当前排列；插入压进相关段队列，反转只改段顺序/标记，删除打全局标记。查询定位第 p 个位置所在段，清理队首已删除元素取最小候选。每块重建一次，整体为根号分治复杂度。",
            "primary_topic": "数据结构",
        },
        "2029F": {
            "statement_brief": "给一个红蓝边染色的环，判断任意两点之间是否都存在边颜色序列为回文的游走。",
            "transformed_statement": "把题目先看成：两端同时沿相同颜色边移动，问题变成任意两点能否通过这种同步过程相遇；连续同色边段的奇偶性决定障碍。",
            "key_observations": [
                "若环上同时存在 RR 和 BB 两种相邻同色边，可选对应位置构造永远无法同步相遇的反例。",
                "只存在一种颜色的连续段时，分析该颜色每个连续段长度的奇偶即可。",
                "所有连续段都是奇数会把两人锁在不同侧，失败。",
                "恰有一个偶长度连续段可以改变同步侧向，从而让所有点对可相遇；全同色或几乎全同色是直接成功特例。",
            ],
            "solution_brief": "关键观察：回文游走等价于从两端同时走相同颜色边，直到相遇。先排除同时有红红和蓝蓝相邻的情况；否则只看唯一会连续出现的颜色的 run。若全同色或同色边至少 n-1 条则可行；一般情况下，恰好一个偶长度 run 才能提供换侧能力，否则存在无法相遇的点对。",
            "primary_topic": "图论与网络流",
        },
        "2027C": {
            "statement_brief": "数组长度会变化。若某个原始位置 i 满足 a_i=当前长度+1-i，就可在末尾追加 i-1 个 0。求最终最大长度。",
            "transformed_statement": "把题目先看成：每个原始位置只是在某个特定长度 u_i 可触发，并把长度跳到 v_i；于是问题是从初始长度 n 出发的有向图可达最大点。",
            "key_observations": [
                "追加出来的 0 永远不会满足触发条件，所以只需考虑原始 n 个位置。",
                "位置 i 的触发长度是 u_i=a_i+i-1，触发后长度变为 v_i=u_i+i-1。",
                "所有转移都是从较小长度到较大长度，图很稀疏。",
                "从 n 开始 DFS/BFS 或按长度扫描可达边，取访问到的最大长度。",
            ],
            "solution_brief": "关键观察：把动态数组变成静态图。对每个原位置 i 建边 a_i+i-1 -> a_i+2i-2；当前长度等于边起点时才可走这条边。追加零不会产生新边，因此从节点 n 在稀疏图上搜索，最大可达长度就是答案。",
            "primary_topic": "图论与网络流",
        },
        "2023C": {
            "statement_brief": "给两个强连通有向图，且每个图所有环长都能被 k 整除。每个点有入/出类型，要在两图之间加 n 条边，保持所有环长仍被 k 整除，判断是否可行。",
            "transformed_statement": "把题目先看成：这种强连通图可以按模 k 分层染色，使每条原边都从颜色 c 指向 c+1；新增边也必须保持这个颜色不变量。",
            "key_observations": [
                "若所有环长都是 k 的倍数，则可给点染成 k 个模层，每条边颜色加一。",
                "新增边从出点连到入点，也必须让跨图后的颜色关系不破坏环长模 k。",
                "固定两图染色后，只需比较每个颜色层的出点数量和目标入点数量。",
                "第二张图整体颜色可循环平移，所以最终检查两个计数数组是否存在循环位移相等。",
            ],
            "solution_brief": "关键观察：先抽出“边让颜色加一”的模 k 不变量。任选起点 DFS/BFS 给每个图染色，并验证边关系；然后按颜色和入/出类型统计需求。第二个图的染色整体可平移，因此把一个计数数组复制一遍，用字符串匹配或 KMP 检查另一个数组是否是它的循环位移。",
            "primary_topic": "图论与网络流",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2237I1": {
            "statement_brief": "给一棵有固定儿子顺序的有根树，非根点可染 0 或 1；染色决定一种介于深搜和广搜之间的遍历，求所有合法染色能产生多少种不同遍历序。",
            "transformed_statement": "把题目先看成：每个点到根路径上的 1 的数量决定第一关键字，原树深搜序决定第二关键字；遍历序就是按这两个关键字排序。",
            "key_observations": [
                "切掉父子间颜色为 1 的边后，每个连通块内部按深搜序输出，块之间按层数广搜。",
                "因此一个染色产生的序列等价于按 d 值、深搜序二关键字排序。",
                "若 d>=x+1 的节点正好是 d>=x 节点按深搜序的后缀，就能把对应 1 链改成 0 而不改变遍历序。",
                "答案等于没有这种坏链的 0/1 染色数，用树上动态规划计数。",
            ],
            "solution_brief": "关键观察：混合遍历可以完全换成排序问题。令 d 为根到点路径上的 1 数量，输出序就是按 (d, 深搜序) 排序。会产生重复的唯一原因是某层之后的节点在深搜序中形成后缀，这时一整条 1 链降层也不改变序列。于是计数不同遍历序等价于计数不存在坏链的染色，按树结构做动态规划。",
            "primary_topic": "树结构",
        },
        "2234F": {
            "statement_brief": "环上有 n 个连通容器，相邻容器的连通口高度为 h_i。对每个指定空容器 i，求其它容器最多能装的总水量。",
            "transformed_statement": "把题目先看成：固定空容器 l 后，某个容器能装的高度由从 l 顺时针和逆时针走到它时遇到的最高连通口共同限制。",
            "key_observations": [
                "若水位超过某条连通口高度，相邻两个容器水位必须相等，否则会违反条件。",
                "固定空点 l，容器 i 的最大水位是两侧路径最大高度的较小值。",
                "选择一个全局最高边作为断点后，左右两侧公式分离成前缀/后缀最大值求和。",
                "所有后缀最大值和可用单调栈在线维护，每个高度进出栈一次。",
            ],
            "solution_brief": "关键观察：先固定空容器，把最大可行水位写成 min(顺时针路径最大口高, 逆时针路径最大口高)。再以一条最高连通口断环，最高值会吃掉一侧的限制，问题变成对每个位置求一段后缀最大值之和。用单调栈维护最大值分段及其贡献，正反各扫一遍即可得到所有答案。",
            "primary_topic": "数据结构",
        },
        "2189D1": {
            "statement_brief": "给 0/1 串 s 和整数 c。对每个候选串 w，f(w) 表示满足每个最小未出现值是否出现要求的排列数量；本版本无问号，求 f(s) 是否不被 c 整除，不行则 -1。",
            "transformed_statement": "把题目先看成：按 0,1,... 依次把新数插入当前排列；第 k 个位置的最小未出现值条件只决定新数是插到两端还是中间。",
            "key_observations": [
                "w_1 或 w_n 为 0 时无合法排列，因为单个 0 和全排列对应的最小未出现值一定出现。",
                "插入数 k 时，插在两端会让最小未出现值 k 可由一段实现，共 2 种选择。",
                "插在中间会把小于 k 的数分到两侧，使最小未出现值 k 无法由一段实现，共 k-1 种选择。",
                "所以 f(w) 是这些局部因子的乘积；判断能否被 c 整除时逐因子用最大公约数消掉 c。",
            ],
            "solution_brief": "关键观察：不要枚举排列，而是按值从小到大插入。每个 k 的要求独立贡献一个因子：要出现最小未出现值 k 就只能插两端，否则插中间有 k-1 种。乘积就是 f(s)。为了判断是否被 c 整除，不必大整数计算，边乘边用最大公约数把 c 的因子约掉；若最后 c 变成 1，则答案为 -1。",
            "primary_topic": "组合计数与概率",
        },
        "2173A": {
            "statement_brief": "一天有 n 节课，重要课必须听；听完重要课后的 k 节也不能睡。求最多能睡多少节非重要课。",
            "transformed_statement": "把题目先看成：某节非重要课能睡，当且仅当它左侧最近的重要课距离超过 k。",
            "key_observations": [
                "重要课本身不能睡，且会覆盖后面 k 个位置。",
                "判断一个 0 是否能睡，只需要最近一次出现的 1，不需要看所有重要课。",
                "从左到右维护 last，若 i>last+k 就计入答案。",
            ],
            "solution_brief": "关键观察：覆盖区间只向右延伸。扫描字符串，遇到重要课就更新最近位置 last；遇到非重要课时，如果它已经超过 last+k，就没有任何之前的重要课能影响它，可以睡。这样直接线性计数。",
            "primary_topic": "基础实现与模拟",
        },
        "2150C": {
            "statement_brief": "商店里每件物品只有一份，Alice 和 Bob 各有偏好序；他们轮流买当前自己最喜欢的剩余物品。问 Alice 可能买到的物品集合中，你给出的价值和最大是多少。",
            "transformed_statement": "把题目先看成：先把 Alice 偏好重编号成 1..n；一个集合 S 可由 Alice 拿到，当且仅当所有不在 S 且编号更小的物品，在 Bob 序中也排在对应 S 物品之前。",
            "key_observations": [
                "若 x 不属于 S、y 属于 S 且 x<y，但 Bob 更喜欢 y，则两人都不会先拿 x，y 就无法按计划归 Alice。",
                "上述条件也充分：Alice 想拿的物品被卡住时，让 Bob 持续拿掉挡在前面的非 S 物品即可。",
                "状态可按扫描到的 Alice 编号和 Bob 已拿物品的最大位置写动态规划。",
                "转移对一段 Bob 位置做加值或取最大，用懒线段树优化到 n log n。",
            ],
            "solution_brief": "关键观察：先刻画 Alice 能拿到哪些集合。重编号后，S 合法等价于不存在 x∉S、y∈S、x<y 且 Bob 位置 x 在 y 后面的冲突。于是从小到大扫物品，维护 Bob 已拿物品的最大位置 j；让 Alice 拿当前物品要求 pos_i>j，让 Bob 拿则更新 j。这个动态规划可用线段树维护最大值和区间加。",
            "primary_topic": "数据结构",
        },
        "2143F": {
            "statement_brief": "给数组和多次区间询问。区间内允许用前面位置的值异或到后面位置，问能否把该子数组变成严格递增序列。",
            "transformed_statement": "把题目先看成：位置 j 能变出的值，正好是区间左端到 j 的线性基能表示出的所有异或值；问题变成能否按下标顺序选出递增可表示值。",
            "key_observations": [
                "允许操作只从左影响右，所以 a_j 的可达集合由前缀线性基决定。",
                "对每个左端 l，维护后缀线性基发生变化的关键位置即可。",
                "线性基可支持统计小于某值的可表示数数量，也可求第 k 小可表示数。",
                "预处理每个 l 最远能延伸到的 r，询问只需比较 r 是否超过这个边界。",
            ],
            "solution_brief": "关键观察：把操作能力翻译成线性基表示能力。固定左端 l 后，随着右端扩大，可表示空间只在插入独立元素时变化；用后缀线性基记录这些变化点。再用线性基的排名/第 k 小能力，按下标块模拟能否选出严格递增值，得到每个 l 的最远合法右端，查询 O(1) 回答。",
            "primary_topic": "数据结构",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2128E2": {
            "statement_brief": "给数组和最小长度 k，找出所有能成为某个长度至少 k 子数组中位数的值，并为每个值给出一个对应区间。",
            "transformed_statement": "把题目先看成：所有可作为子中位数的值会形成一个连续值域；只要找出最小和最大子中位数，再沿区间端点移动路径补出中间值。",
            "key_observations": [
                "若 x 和 y 都是子中位数，那么 x 到 y 之间的每个 z 也是子中位数。",
                "证明思路是把一个见证区间连续移动到另一个见证区间，端点每次只变一步，中位数条件不会跳过中间值。",
                "先用简单版方法找最小和最大子中位数及其区间。",
                "扫过连接两区间的移动路径，用维护当前区间中位数的数据结构给每个中间值记录见证。",
            ],
            "solution_brief": "关键观察：困难版不是对每个值独立判定，而是利用子中位数集合的连续性。先求最小、最大可行值；把对应两个区间通过移动左右端点连接成一条离散连续路径。路径上相邻区间只差一个元素，因此中位数不会跨过中间值；边移动边维护当前区间的上下半部分，就能给所有中间值填见证区间。",
            "primary_topic": "数据结构",
        },
        "2118D2": {
            "statement_brief": "数轴上有周期为 k 的红绿灯，从给定起点和方向出发，遇红灯就掉头，否则继续走。多次询问是否最终会离开长条。",
            "transformed_statement": "把题目先看成：一次真正改变状态只发生在撞到红灯时；状态由红灯编号和进入方向决定，若同一状态重复就成环。",
            "key_observations": [
                "向右走会撞到满足 (d_i-p_i) mod k 等于当前 (t-x) mod k 的下一盏灯。",
                "向左走同理按 (d_i+p_i) mod k 分组查找上一盏灯。",
                "每个红灯每个方向的后继状态固定，可以预先建成函数图。",
                "查询从起点先找第一次会撞到的灯，再沿函数图走；记忆化或环检测即可回答。",
            ],
            "solution_brief": "关键观察：逐秒模拟是假的难点，真正状态只在红灯处改变。按 d_i-p_i 和 d_i+p_i 的模 k 值分组，用有序位置集合找到当前方向上第一盏会红的灯。之后每个“灯+方向”都有固定后继，形成函数图；预处理或记忆化判断该状态最终出界还是进环，每个询问只需接入这张图。",
            "primary_topic": "图论与网络流",
        },
        "2102B": {
            "statement_brief": "数组中每个数可任意次取相反数，绝对值两两不同。判断能否让第一个元素成为整个数组的中位数。",
            "transformed_statement": "把题目先看成：符号只决定一个数在正负两侧，真正重要的是 |a_1| 在所有绝对值中的排名。",
            "key_observations": [
                "先把所有数取绝对值，原始符号和原顺序都不影响可行性。",
                "若 |a_1| 足够小，可以把更大的数按需要取负，让 a_1 排到中位数位置。",
                "若 |a_1| 太大，取反其它数只会把它推得更靠边，取反自己也无法补足较小绝对值数量。",
            ],
            "solution_brief": "关键观察：只看绝对值排名。排序所有 |a_i|，若 |a_1| 属于前 floor(n/2)+1 小，就能通过给较大绝对值选符号把它调成中位数；否则较小绝对值太多，无论怎么翻符号都无法让第一个元素处在中位数位置。",
            "primary_topic": "基础实现与模拟",
        },
        "2101F": {
            "statement_brief": "树上每个点可染红、蓝、白。一个染色的酷度是最远红点和蓝点距离，求所有 3^n 个染色的酷度总和。",
            "transformed_statement": "把题目先看成：对每个染色的红蓝直径，给它找一个唯一的中心证书：要么是特殊点，要么是特殊边，然后按证书计数贡献。",
            "key_observations": [
                "所有最长红蓝路径两两相交，它们的交集是一条非空简单路径。",
                "若存在点到最远红点距离加到最远蓝点距离等于直径，它就是特殊点；否则会出现特殊边。",
                "把非特殊点指向同时包含最远红蓝点的那个儿子，可形成辅助有向结构来证明特殊点/边的划分。",
                "最后按每个特殊点或特殊边作为中心，统计两侧颜色选择对总答案的贡献。",
            ],
            "solution_brief": "关键观察：不要枚举染色后再找直径，而是反过来按直径中心计数。对任意染色，所有合法红蓝直径相交；若交集中有满足两端最远距离和等于直径的点，就归到特殊点，否则归到夹在两侧的特殊边。这个唯一证书把计数拆到树的局部方向上，用动态规划累计各中心贡献。",
            "primary_topic": "树结构",
        },
        "2090A": {
            "statement_brief": "两个人轮流挖宝，第一人每天挖 x 米，第二人每天挖 y 米；宝藏深度为 a+0.5，问谁第一次挖超过深度。",
            "transformed_statement": "把题目先看成：每两天固定推进 x+y 米，只需要看完整周期后的剩余深度由谁补上。",
            "key_observations": [
                "整对回合不会改变先后手关系，只需看 a 对 x+y 的余数。",
                "若余数小于 x，第一人当天就超过 a+0.5。",
                "否则第一人挖完还没超过，第二人会在当天超过。",
            ],
            "solution_brief": "关键观察：把两天看成一个周期。跳过所有完整的 x+y 后，剩余阈值只由 a%(x+y) 决定；若它小于 x，则第一人先挖到超过 a+0.5，输出第一人的结果，否则第二人先挖到。",
            "primary_topic": "基础实现与模拟",
        },
        "2077D": {
            "statement_brief": "给数组，要求选出字典序最大的子序列，使它能作为一个多边形的边长；不存在则输出 -1。",
            "transformed_statement": "把题目先看成：若固定子序列最大边 x，可以贪心维护字典序最大候选；而真正需要尝试的 x 只会来自数组里最大的少量元素。",
            "key_observations": [
                "多边形条件等价于长度至少 3 且总和大于最大边的两倍。",
                "固定最大边 x 时，从左到右维护字典序最大子序列；若替换最后一个元素后仍能靠右侧元素凑够总和，就替换。",
                "若一个递增多重集没有任何可组成多边形的子序列，其元素必须像斐波那契式增长，数量只有 O(log A)。",
                "因此最优答案的最大边一定在全局最大的 O(log A) 个元素中。",
            ],
            "solution_brief": "关键观察：最大边不用枚举全部 n 个。若一批最大的数中没有任何三边能成多边形，则它们必须满足每个数都大于前面总和，数量受值域对数限制。于是只枚举最大的约 log A 个候选最大边；对每个 x 线性贪心求字典序最大且总和能超过 2x 的子序列，取全局最优。",
            "primary_topic": "构造与贪心",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2059C": {
            "statement_brief": "有 n 个队列，连续 n 个时刻每个队列都会增加人数，然后选择一个队列清零。最终得到各队列人数，要求让最小未出现值尽量大。",
            "transformed_statement": "把题目先看成：想让最终出现 0,1,2,...，对应的队列必须分别在最后、倒数第二、倒数第三等时刻被服务，并且末尾连续增量全为 1。",
            "key_observations": [
                "最后一次被清空的队列最终一定为 0，所以 0 总能保证。",
                "若某队列最终为 t，它最后一次清零后面的 t 个增量必须全部为 1。",
                "每个队列能提供的最大小值，只由它末尾连续 1 的长度决定。",
                "从小到大贪心选择能覆盖当前值的最短后缀队列，就能最大化最小未出现值。",
            ],
            "solution_brief": "关键观察：最终值 t 只能由“倒数 t 个时刻都加 1，且更早某刻清零”的队列产生。于是每个队列先算末尾连续 1 的长度 m，它可以承担 0..m 中的某个值。把这些 m 排序，从 0 开始贪心找第一个 m>=当前需求的队列，需求加一；失败处就是答案。",
            "primary_topic": "构造与贪心",
        },
        "2057H": {
            "statement_brief": "一排咖啡机中有学生，关闭某个内部房间会把其中学生一半向左、一半向右移动。对每个集合点，求最多能把多少学生聚到那里。",
            "transformed_statement": "把题目先看成：固定目标 k 后，目标点不能操作；目标两侧能做的操作都应尽早做，问题变成模拟一侧的贪心传递。",
            "key_observations": [
                "若想最大化 k 处人数，除 k 外的可执行操作不会伤害答案，能做就做。",
                "一侧稳定后，每个位置最终只剩 0 或 1，额外学生会像进位一样向边界传递。",
                "用栈维护当前前缀里为 0 的位置，可以批量模拟连续传递过程。",
                "正向和反向各处理一次，即可得到每个 k 从左侧和右侧能收到的贡献。",
            ],
            "solution_brief": "关键观察：固定目标后，所有非目标位置的操作顺序可以贪心化。处理一侧时，把学生数超过 1 的位置看成会不断向外产生贡献，内部状态最终只需记录哪些位置是 0。用栈维护 0 的位置并批量推进“进位”，可在线求出每个边界收到的学生数；左右两侧相加得到每台机器的答案。",
            "primary_topic": "数据结构",
        },
        "2053B": {
            "statement_brief": "每个位置 i 的真实值 w_i 只能在区间 [l_i,r_i] 内选择。对每个 i，问是否存在一种赋值让 w_i 与所有其它位置都不同。",
            "transformed_statement": "把题目先看成：只有区间长度为 1 的位置会强迫占用某个值；长度大于 1 的位置总能避开指定值。",
            "key_observations": [
                "若另一个位置也是可变区间，它至少有两个选择，可以避开 w_i。",
                "阻止 i 唯一的，只可能是某些固定值区间 [x,x]。",
                "若 i 本身固定为 x，则只有当还有别的位置也固定 x 时才失败。",
                "若 i 是区间，则只要区间内存在一个没有被固定占用的值，就能选它变唯一。",
            ],
            "solution_brief": "关键观察：可变区间不会真正堵死一个值，固定点才会。统计每个值被多少个 [x,x] 占用，并做是否被占用的前缀和。固定位置看 cnt[x] 是否为 1；非固定位置看 [l_i,r_i] 中是否存在未被任何固定点占用的值。",
            "primary_topic": "构造与贪心",
        },
        "2053A": {
            "statement_brief": "给数组，要把它分成连续段，使每段中任取三个数都能组成非退化三角形；问是否至少有两种划分。",
            "transformed_statement": "把题目先看成：全切成单点永远合法；想有第二种划分，只需要找到一个合法的长度 2 段。",
            "key_observations": [
                "稳定集合的任意非空子集仍稳定，所以合法长段可以继续切小。",
                "因此只要存在任意一种非全单点划分，就一定存在只有一个长度 2 段的划分。",
                "两个数 x,y 组成的集合稳定，当且仅当 2*min(x,y)>max(x,y)。",
            ],
            "solution_brief": "关键观察：不用考虑复杂分段。单点划分总是一个答案；第二种划分存在等价于某个相邻二元集合稳定，因为任何更长合法段都能切到长度 2 仍合法。扫描相邻对，只要满足 2*min>a 的最大值条件就输出可行。",
            "primary_topic": "几何",
        },
        "2031A": {
            "statement_brief": "给一个本来非增的柱高数组，每次可把任意柱子改成任意正整数，求最少改几根使数组变成非降。",
            "transformed_statement": "把题目先看成：在非增数组里，若两根不同高度的柱子都不改，它们的相对顺序会与非降要求冲突；所以不改的柱子必须同高。",
            "key_observations": [
                "目标是最大化保留下来的柱子数量。",
                "非增数组中，两个不同高度的未改柱子一定前高后低，无法同时满足最终非降。",
                "选出现次数最多的高度全部保留，其它柱子都改成这个高度即可达到下界。",
            ],
            "solution_brief": "关键观察：最优不是维护最长非降子序列，而是所有未修改元素必须相等。因为原数组非增，任意两个不同高度若都保留就会形成下降。于是最多保留某个高度的全部出现次数，答案是 n 减去最高频次。",
            "primary_topic": "基础实现与模拟",
        },
        "2028D": {
            "statement_brief": "Alice 从 1 号牌开始，想通过与三位对手交换逐步得到 n 号牌；每个对手都有自己的牌偏好，只有觉得换到的牌更好才愿意交换。要求判断并构造交易链。",
            "transformed_statement": "把题目先看成：从大牌往小牌倒推。若当前牌 a 能换到某个已经能到 n 的更大牌 b，就说明 a 也能到 n。",
            "key_observations": [
                "对固定对手，a 能换到 b 的条件是 b>a 且该对手更喜欢 a 胜过 b。",
                "倒序扫描时，只需知道每位对手在所有可达 b 中偏好值最小的那个 b。",
                "若 p_a 大于这个最小偏好值，就能通过该对手跳到对应 b。",
                "记录前驱牌和使用的对手即可从 1 还原交易方案。",
            ],
            "solution_brief": "关键观察：三位对手不用建完整图。设已经知道哪些更大编号能到 n；对每位对手，只维护这些可达牌中偏好排名最低的代表 b。倒序检查 a 时，如果某位对手愿意用 b 换 a，就把 a 标为可达，并用 a 更新三位对手的最优代表。最后沿记录的下一张牌输出交易链。",
            "primary_topic": "图论与网络流",
        },
        "2022E2": {
            "statement_brief": "部分填好的整数网格要求任意子矩形四角异或为 0，之后不断给空格填值；每个状态求合法补全数量。",
            "transformed_statement": "把题目先看成：美丽网格等价于行点和列点组成的二分图边权约束；每个已填格子是一条边，环上边权异或必须为 0。",
            "key_observations": [
                "四角异或为 0 等价于存在行势能和列势能，使格子值等于二者异或。",
                "已填格子就是行列二分图中的带权边；矛盾只会在新增边形成非零异或环时出现。",
                "边只增加，所以第一次出现矛盾后，后续答案恒为 0。",
                "无矛盾时，自由度只由连通块数量决定；可用带权并查集在线维护。",
            ],
            "solution_brief": "关键观察：把网格条件转成图势能。每个格子 (r,c)=x 表示行点 r 与列点 c 的异或差为 x；若两点已连通，就检查路径异或是否等于 x，否则合并并记录到根的异或值。只要出现一次冲突，后面全为 0；否则答案按当前连通块数量给出幂次。",
            "primary_topic": "图论与网络流",
        },
        "2258B2": {
            "statement_brief": "给若干胡萝卜长度和多组切割次数 k；每次可选择若干胡萝卜按同一长度 x 切一刀，问恰好 k 次后最多能卖出多少段等长胡萝卜。",
            "transformed_statement": "把题目先看成：固定目标长度 x 后，最优切割长度应按 x*2^(k-1), x*2^(k-2), ..., x 的顺序做。",
            "key_observations": [
                "一根长度 a 对目标 x 的贡献最多是 min(floor(a/x), 2^k-1)，整倍特殊情况可达到 2^k。",
                "k 很大时每根贡献已被长度本身限制，答案接近总长度。",
                "最优 x 不需要太大，超过 m/2^k 后不会产生更好贡献。",
                "对所有 x 的贡献可用前缀和按商分段统计。",
            ],
            "solution_brief": "关键观察：先固定最终要卖的长度 x。k 次切割能制造的 x 段数有明确上界，最佳切割顺序是按 x 的二倍幂从大到小切，让每根尽量拆成 x 段。于是每根贡献可写成关于 floor(a_i/x) 的截断函数；对所有 x 用前缀和和商分块累计，得到每个 k 的最大值。",
            "primary_topic": "构造与贪心",
        },
        "2257B": {
            "statement_brief": "两名巨人站在各自按非增高度排列的山上轮流攻击对方脚下的山；山降到需要换山，无法继续者输。判断谁先失败。",
            "transformed_statement": "把题目先看成：一个巨人在整条山脉上能承受的攻击次数，会望远镜式抵消成第一座山高度加山数减一。",
            "key_observations": [
                "站在某座山时，每次攻击让该山高度减少 1。",
                "从第 i 座换到第 i+1 座，总共经历 a_i-a_{i+1}+1 次相关变化。",
                "把所有段相加后中间高度全部抵消，只剩 a_1+n-1。",
            ],
            "solution_brief": "关键观察：不用模拟每一击。山高非增，某人从第一座走完整条山脉前的有效回合数为 (a_1-a_2+1)+...+(a_{n-1}-a_n+1)+a_n=a_1+n-1。另一人同理，比较两个数即可。",
            "primary_topic": "基础实现与模拟",
        },
        "2228D": {
            "statement_brief": "平面上有 n 个整点。用一条竖线和一条横线把点分成四象限且每象限非空，按象限给点染四种颜色；求不同染色数量。",
            "transformed_statement": "把题目先看成：真正不同的染色只会在分割线跨过某个点坐标时改变；固定竖线后，要数左右两侧可行横线区间的交集。",
            "key_observations": [
                "相邻两条横线若左右两侧点集不变，就产生同一种染色，不能重复计数。",
                "固定左侧点集后，左边要上下都非空会给出若干 y 区间，右边也给出若干 y 区间。",
                "合法染色对应左右可行 y 区间有交。",
                "扫描竖线并动态维护这些区间，用树状数组或集合统计交叠数量。",
            ],
            "solution_brief": "关键观察：把二维染色去重转成区间交计数。按 x 扫描竖分割线，只在点跨边时更新；对当前左右点集，各自能让上下非空的横线位置形成若干区间。一个真正合法且新的四象限染色对应一对左右区间存在交点，动态维护区间集合即可计数。",
            "primary_topic": "几何",
        },
        "2215C": {
            "statement_brief": "通信交互题：第一段程序知道 n 和隐藏数 s，但不知道树；它要在树边逐条出现时定向。第二段程序只看到定向树，要恢复 s。",
            "transformed_statement": "把题目先看成：树边方向可以编码端点二进制标记是否相同；第二段程序沿树遍历即可恢复所有点标记。",
            "key_observations": [
                "共有 2^(n-1) 个可能的 s，正好可用 2..n 号点各承载一位。",
                "对边 (u,v)，若两个端点标记相同就按编号小到大定向，否则反向定向。",
                "第二段程序以 1 号点标记为 0，从边方向判断相邻点标记是否翻转。",
                "树连通无环，沿一次遍历即可恢复所有点标记，再还原 s。",
            ],
            "solution_brief": "关键观察：第一段程序不需要知道整棵树，只要给每个点预先写一位。边出现时，用方向表示两端位是否相同：同位按小编号到大编号，异位反过来。第二段程序拿到整棵有向树后，从 1 号点出发，根据每条边方向推出子点位是否与父点相同，最终读出 2..n 号点的二进制数。",
            "primary_topic": "交互",
        },
        "2192C": {
            "statement_brief": "枪按固定弹匣顺序射击，每轮打完 n 发后装填耗时 k。开战前最多交换两发子弹，求杀死敌人的最短时间。",
            "transformed_statement": "把题目先看成：完整弹匣的总伤害和用时不受交换影响；交换只可能影响最后一个未打满弹匣。",
            "key_observations": [
                "先尽量跳过完整弹匣，只留下最后一轮需要补的剩余血量。",
                "若想用前 i 发结束，最优交换是把前 i 发中的最小伤害与后缀中的最大伤害交换。",
                "预处理前缀和、前缀最小值、后缀最大值，就能 O(1) 判断每个 i。",
                "取第一个能覆盖剩余血量的 i，加上完整弹匣时间即为答案。",
            ],
            "solution_brief": "关键观察：一次交换不会改变任何完整弹匣的总伤害，只会让最后一匣更早打出高伤害。先用总伤害扣掉尽可能多的完整弹匣；对剩余血量枚举最后一匣使用前 i 发，最优操作一定是用后缀最大值替换前缀最小值。用预处理快速算交换后的前缀伤害，找到最小 i。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2164F2": {
            "statement_brief": "给一棵以 1 为根的树和数组 a，要求统计满足条件的排列 p：对每个点 u，根到 u 路径上恰有 a_u 个祖先点的 p 值小于 p_u。",
            "transformed_statement": "把题目先看成：每个点在根路径上的相对大小位置已经由 a_u 唯一决定，剩下是在一个特殊有向图里数拓扑序。",
            "key_observations": [
                "给树顶补最小点和最大点后，每条根路径上的 p 值相对顺序可以递推确定。",
                "插入新点 u 时，它只是在路径顺序里某条已有约束边 s->t 中间插入 s->u->t。",
                "反向删除入度、出度都为 1 的点，可以把特殊有向图逐步缩回一条边。",
                "每次缩边时，三部分内部拓扑序固定，只需用组合数统计相互穿插方式。",
            ],
            "solution_brief": "关键观察：不要直接对排列计数，而是把 a_u 转成偏序约束。补上全局最小和最大点后，点 u 的位置就是根路径顺序中的第 a_u 与第 a_u+1 个点之间，因此构图过程等价于不断把一条边细分成两条边。按反向过程删除这种二度点，维护每条边代表的子图大小和拓扑序数量，缩到最后一条边即为答案。",
            "primary_topic": "树结构",
        },
        "2127H": {
            "statement_brief": "给一个 n≤30 的连通无向图，每个点属于的简单环不超过 5 个，求最多能选多少条边，使选出的子图中每个点度数不超过 2。",
            "transformed_statement": "把题目先看成：目标子图的每个连通块只能是路径或环；用 DFS 树的中心点切开图，再在小连通块上做状态压缩。",
            "key_observations": [
                "任取 DFS 树，经过同一个点的返祖边不超过 5 条，否则该点会在太多简单环中。",
                "选 DFS 树重心 v 后，枚举经过 v 的返祖边是否保留，并相应扣掉端点可用度数。",
                "删除 v 和这些返祖边后，每个剩余连通块大小至多约为 n/2。",
                "每个小块用状态压缩动态规划选择若干路径，再可选择把路径闭成环。",
            ],
            "solution_brief": "关键观察：限制“每点至多 5 个环”让经过任一点的返祖边数量很小。取 DFS 树重心 v，暴力枚举穿过 v 的返祖边，删除 v 后所有组件大小被压到一半。组件内目标结构只有路径和环，于是用 bitmask DP 维护已用点集合和当前路径两端，计算在剩余度数限制下最多选边数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2122E": {
            "statement_brief": "给一个部分填好的 2×n 网格，空格要填 1..k，要求任意子网格里都存在一条贪心路径，其路径和等于所有向右/向下路径中的最大值。",
            "transformed_statement": "把题目先看成：2 行网格的路径只是在某一列从上行切到底行；每个切点收益由差分 c_i=a_{i+1}-b_i 的前缀和决定。",
            "key_observations": [
                "固定一个 2×区间，最优路径等价于选一个差分前缀和最大的切换位置。",
                "贪心路径会沿着 c_i≥0 的最长前缀走，然后在下一列切下去。",
                "因此合法条件等价于：每次遇到负差分后，之后累积和不能变成正数。",
                "差分值范围在 [-k,k]，负值会重置状态，非负值只在 [-k,0] 内累计，可以按列做 DP。",
            ],
            "solution_brief": "关键观察：把网格路径和写成差分前缀和后，贪心选点和最优选点都变成前缀最大值问题。对所有子网格成立，等价于每段从第一个负差分之后开始的累积和始终不超过 0。于是逐列枚举可填出的差分 c_i，用状态 j 表示最近一次负差分后的累积和，j 只需落在 [-k,0]，动态规划计数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2119E": {
            "statement_brief": "给 a_1..a_{n-1} 和初始 b_1..b_n，每次只能把某个 b_i 加 1，求最少操作数使所有相邻按位与满足 b_i & b_{i+1}=a_i，若不可能则输出 -1。",
            "transformed_statement": "把题目先看成：每个 b_i 最终必须包含左右相邻 a 的并集；在这个强制掩码之上，真正可能成为最优值的候选只有约 31 个进位断点。",
            "key_observations": [
                "b_i 至少要包含 a_{i-1}|a_i，否则某条相邻约束必然无法满足。",
                "从当前 b_i 往上加时，只有把某一位进成 1 并把低位清零的台阶值可能成为最优。",
                "将这些台阶值再或上强制掩码，就得到每个位置的少量有效候选。",
                "相邻两个候选只需检查按位与是否等于对应 a_i，然后做最短路式 DP。",
            ],
            "solution_brief": "关键观察：不能在所有整数上 DP，只需要枚举每个位置的有效台阶值。先算必须拥有的掩码 need_i=a_{i-1}|a_i；再从原 b_i 出发生成“升到下一高位、低位清零”的候选，并统一或上 need_i。每个位置约 31 个候选，转移时检查 x&y 是否等于 a_i，代价是候选值减原值，取最小即可。",
            "primary_topic": "动态规划与状态设计",
        },
        "2113E": {
            "statement_brief": "树上 Marat 从 x 去 y，敌人各自按最短路从家到单位移动；Marat 每步可走或停，不能在同一时刻与敌人在同一顶点，求最早到达时间或判无解。",
            "transformed_statement": "把题目先看成：每个时刻有一批禁用点；只需要维护 Marat 当前可能所在的点集，并处理点集边界的扩张和禁用删除。",
            "key_observations": [
                "如果答案存在，最晚到 2n+1：n+1 时敌人都已到达，再走最多 n 步即可。",
                "敌人路径产生的坏点时刻总量至多是所有路径长度之和。",
                "可达点集从 t 到 t+1 只会加入旧集合的邻居，再删掉下一时刻有敌人的点。",
                "一个点每次离开都由某次敌人占据导致，因此重新进入次数总量可控。",
            ],
            "solution_brief": "关键观察：不需要做完整 n×时间 的暴力扩张。先记录每个时刻的敌人占据点；维护当前可达集合 S。下一时刻，旧 S、S 的邻居都可能可达，但要删除坏点。只把新进入点的邻居放入候选，并把刚解除禁用的点重新尝试；每个点进入次数受敌人经过次数限制，总复杂度按敌人路径总量控制。",
            "primary_topic": "图论与网络流",
        },
        "2108F": {
            "statement_brief": "数组表示一排塔高，每座塔必须恰好推倒一次；推倒第 i 座会给后面 a_i 座塔各加 1 并把自己清零，求最终非降数组的最大最小未出现值。",
            "transformed_statement": "把题目先看成：如果某个最终数组可达，那么把任意位置高度再降低也仍可达；所以可行的最小未出现值具有单调性。",
            "key_observations": [
                "某塔最终高度等于它倒下之后还会落到它身上的块数。",
                "若能得到数组 A，则可以调整倒塔顺序得到任意逐点不超过 A 的数组。",
                "因此要实现 MEX=x，只需检查能否得到形如若干 0 后接 1,2,...,x-1 的非降数组。",
                "检查时从左到右扫描，用差分维护当前已落到该塔上的块数。",
            ],
            "solution_brief": "关键观察：可达集合对逐点降低是封闭的，所以答案可以二分。检查 x 时，把目标简化为非降数组中包含 0..x-1，即后缀依次放这些值、前面全是 0。扫描每座塔，维护已有落块数；当当前位置需要目标高度 h，就安排它在恰好 h 个未来落块之后倒下，并把它倒下产生的影响加入差分。",
            "primary_topic": "构造与贪心",
        },
        "2097D": {
            "statement_brief": "给两个 01 串 s 和 t。允许对偶数长度串递归分半，并把一半按位异或到另一半，问能否把 s 变成 t。",
            "transformed_statement": "把题目先看成：把长度 n 写成 2 的幂乘奇数 m，再把字符串按行切成矩阵；所有操作本质上是在二元域上做可逆行变换。",
            "key_observations": [
                "奇数宽 m 不会继续被分半，所有递归操作都只混合行，不混合列。",
                "题目允许的递归分半和异或操作能够生成任意可逆行变换。",
                "因此两个字符串可互达，当且仅当对应矩阵的行空间相同。",
                "把两个矩阵都做高斯消元成唯一的行最简形，比较即可。",
            ],
            "solution_brief": "关键观察：操作看似递归，其实完整等价于对矩阵行做可逆线性变换。令 n=2^k*m 且 m 为奇数，把字符串切成 2^k 行、m 列的 0/1 矩阵。题解证明这些操作能实现任意可逆行变换，所以 s 能到 t 等价于两个矩阵有同一个行空间；分别高斯消元后比较标准形。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2081E": {
            "statement_brief": "树边上有带颜色和编号的筹码，筹码只能在自己的根到 d_i 路径范围内上下移动，同色相邻可交换；最终全部回到根边，求可能的最终编号排列数。",
            "transformed_statement": "把题目先看成：先按编号从大到小把每个筹码推到能到的最深边；之后只需考虑各子树筹码向上合并时，同色连续段如何穿插。",
            "key_observations": [
                "先把筹码尽量下推不会损失可达性，之后所有最终排列都能由上移和同色交换得到。",
                "合并两个子树时，真正影响后续的不是完整序列，而是顶部颜色和顶部同色连续段长度。",
                "同色段相接时有组合数种穿插方式；异色段相接时要枚举分裂顶部同色段的位置。",
                "树上背包合并这些状态，总规模按筹码数平方控制。",
            ],
            "solution_brief": "关键观察：先做一个规范初态：按编号降序把每个筹码下推到可达的最深位置。之后自底向上把子树筹码合并到父边，状态只保留顶部颜色和顶部最长同色段长度，因为只有这里会和父边原有筹码发生新的同色交换。每次合并用组合数统计穿插方式，得到树形 DP。",
            "primary_topic": "动态规划与状态设计",
        },
        "2066F": {
            "statement_brief": "数组 a 可反复选择当前最大子段和的某个非空子段，并把它替换成任意非空数组；问能否变成数组 b，并构造总替换长度受限的操作序列。",
            "transformed_statement": "把题目先看成：原数组会被一个唯一的“冷分割”切成若干段，段间屏障永远不会被操作跨过；可达数组只能按这些段分别替换。",
            "key_observations": [
                "递归取最长最大子段和段，可以得到唯一分割。",
                "这些分割边界在任何操作序列中都不会被跨过。",
                "选择一个阈值 x 后，和小于 x 的原段必须保持不变；其余段可被替换，但至多一个段可替成完全任意数组。",
                "于是枚举阈值，在分割段和目标数组前缀之间做 DP 匹配。",
            ],
            "solution_brief": "关键观察：先刻画可达集合，而不是直接构造。对 a 递归选最长最大子段和段，得到不会被跨越的分割屏障。可达数组必然对应某个段和阈值 x：小于 x 的段保留，大于等于 x 的段被替换，其中只有一个段能替成任意数组，其余替换段的最大子段和不能超过 x。枚举 x 后用 DP 判断 b 能否按这些段拼出，并反向构造操作。",
            "primary_topic": "动态规划与状态设计",
        },
        "2066C": {
            "statement_brief": "依次把每个 a_i 异或到 P、Q、R 三个变量之一，要求每一步后三个数不能两两不同，求合法操作序列数量。",
            "transformed_statement": "把题目先看成：第 i 步后三个变量的总异或恒等于前缀异或 pref_i；只要有一对相等，第三个数就必须等于 pref_i。",
            "key_observations": [
                "合法状态一定长成 (pref_i,x,x) 及其三个位置排列。",
                "因此 DP 只需要记录那个重复值 x，而不是记录三元组。",
                "从第 i-1 步到第 i 步，除 x=pref_{i-1} 之外，其它状态值都不会改变。",
                "用哈希表维护 dp[x]，每一步只更新一个键。",
            ],
            "solution_brief": "关键观察：P xor Q xor R 永远等于当前前缀异或。若三个数不两两不同，就有两个相等，它们抵消后第三个必为 pref_i，所以所有合法状态只有三种排列形式。设 dp[x] 表示重复值为 x 的方案数；加入 a_i 时只有 dp[pref_{i-1}] 会发生变化，公式为 3*dp[pref_{i-1}]+2*dp[pref_i]，最后求和。",
            "primary_topic": "动态规划与状态设计",
        },
        "2064E": {
            "statement_brief": "给排列 p 和颜色 c，把每个 p_i 高度的同色沙块放入第 i 列后执行重力排序。求有多少对新排列和颜色能得到完全相同的沙块布局。",
            "transformed_statement": "把题目先看成：第一列直接锁死颜色数组；剩下只是在同色元素之间交换 p 值，且交换是否合法由中间异色元素高度限制。",
            "key_observations": [
                "排序后第一列颜色就是原 c，因此新颜色必须等于 c。",
                "只看某一种颜色时，最终布局能反推出该颜色拥有的高度集合。",
                "同色位置 i,j 的高度可交换，当且仅当中间所有异色高度都小于二者高度。",
                "按高度从小到大用并查集合并可互达位置，形成不交或包含的区间结构；每次固定一个位置时乘上当前组件大小。",
            ],
            "solution_brief": "关键观察：颜色不可能改变，因为第一列已经暴露了 c。对同一种颜色，两个高度能否互换只取决于夹在中间的异色高度是否都更低。按 p 值从小到大激活位置，并查集合并当前高度能跨过的同色连通范围；这些可达范围天然呈嵌套结构，不必显式建树，合并时按组件可选位置数累乘即可。",
            "primary_topic": "数据结构",
        },
        "2047A": {
            "statement_brief": "Alyona 每天按固定顺序拼若干拼图块；当当天结束时刚好完成某个以中心为核心的正方形层，就算开心，求开心天数。",
            "transformed_statement": "把题目先看成：累计拼好的块数若等于奇数边长正方形面积，就说明所有已开始的层都完整结束。",
            "key_observations": [
                "中心块对应 1×1，之后每一完整层都会形成边长为奇数的正方形。",
                "拼图顺序固定，所以只需要看每天结束后的累计块数。",
                "预处理或直接判断累计和是否为奇数平方即可。",
            ],
            "solution_brief": "关键观察：完成一层时，当前图形一定是边长 1、3、5、... 的正方形。逐日累加已放块数，如果累计和等于某个奇数的平方，就把答案加一。",
            "primary_topic": "基础实现与模拟",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2034D": {
            "statement_brief": "数组只含 0、1、2，且至少有一个 1。一次操作只能在差值为 1 的两列之间转移一个石刻，相当于交换一个 1 和相邻值 0 或 2；要求用不超过 n 次操作把数组排成非降。",
            "transformed_statement": "把题目先看成：目标位置分成 0 区、1 区、2 区；所有错位元素都可借助值为 1 的位置完成交换。",
            "key_observations": [
                "0 不能直接和 2 交换，但可以通过 1 作中介，用两步完成间接交换。",
                "先修 0 区或 2 区时，当前位置若不是目标值，就找一个可直接交换的 1；没有直接 1 时先把另一侧的 1 调过来。",
                "若先处理数量较少的一端，操作数可压到 n 以内。",
                "维护 value-in-position 的 3×3 桶，就能快速找到需要交换的下标。",
            ],
            "solution_brief": "关键观察：排序目标只有三个区间。值 1 是唯一中介，0 和 2 的错位可以拆成两次与 1 的交换。按 0 的数量和 2 的数量选择先修哪一端；每次从“当前值在错误目标区”的桶中拿下标交换，并同步维护桶。题解证明按较少端优先时总步数不超过 n。",
            "primary_topic": "构造与贪心",
        },
        "2034A": {
            "statement_brief": "给两个数 a,b，求最小整数 m，使 m 至少不小于 a、b 中的一个，并且 m 除以 a 和 b 的余数相同。",
            "transformed_statement": "把题目先看成：若最小 m 的公共余数不是 0，则 m-1 仍满足条件，矛盾；所以答案必须同时整除 a 和 b。",
            "key_observations": [
                "设 m%a=m%b=x。",
                "若 x>0，则 m-1 的两个余数都会同时减 1。",
                "同时 m-1 仍不小于较小的那个数，因此原 m 不可能最小。",
                "所以最小 m 是 a 和 b 的最小公倍数。",
            ],
            "solution_brief": "关键观察：公共余数如果为正，就可以把 m 减一且仍保持两个余数相等，这与最小性矛盾。因此最优 m 的公共余数只能是 0，也就是同时为 a、b 的倍数；输出最小公倍数。",
            "primary_topic": "数论与同余",
        },
        "2196E2": {
            "statement_brief": "给源串 s 和目标串 t，每次可复制 s 的一个子串追加到 p 末尾，并允许在刚追加的这一段中改至多一个字符；求拼出 t 的最少操作次数。",
            "transformed_statement": "把题目先看成：每一步都应贪心取当前 t 后缀能由 s 中某个子串一处修改得到的最长前缀。",
            "key_observations": [
                "若当前一步取短了，下一段能匹配的范围不会因此变长，所以最长前缀贪心正确。",
                "问题核心变成快速求：t 的某个后缀和 s 的某个后缀在允许一处不同下的最长公共前缀。",
                "把 s、t 拼在一起建后缀数组和最长公共前缀结构，可在常数时间比较任意后缀的字典序关系。",
                "枚举修改位置和替换字符，并在 s 的后缀集合中二分插入位置，取相邻后缀给出的最长匹配。",
            ],
            "solution_brief": "关键观察：最优一定是每次吃掉当前剩余 t 的最长可行前缀。为了找这个长度，建 s#t 的后缀数组和区间最小最长公共前缀查询；对允许修改的位置，判断修改后的 t 后缀在 s 后缀排序中的位置，只需看左右最近的 s 后缀即可得到可匹配长度。不断贪心切段，段数就是答案。",
            "primary_topic": "字符串",
        },
        "2190D": {
            "statement_brief": "给一片森林，统计所有把它补成树的方案中，Prufer 删除过程最后除 n 外留下的另一个点分别是谁。",
            "transformed_statement": "把题目先看成：最终 Prufer 顶点就是补成树后从 n 到 n-1 路径上的第二个点；于是只需统计补边后这个第二点为 v 的方案数。",
            "key_observations": [
                "n-1 只有在最后和 n 同时作为两个叶子时才可能不提前被删。",
                "因此 Prufer 顶点等于 n 到 n-1 路径上紧邻 n 的那个点。",
                "补森林时，同一个连通块内的点在连接计数上可按大小对称处理。",
                "先算补成树总方案，再按 v 所在连通块和相对 n、n-1 的位置分情况乘概率因子。",
            ],
            "solution_brief": "关键观察：不用模拟整段 Prufer 过程。只要树固定，最终留下的非 n 点就是 n 到 n-1 路径上的第二个点。于是题目变成森林补边计数：枚举候选 v，根据 v 与 n、n-1 是否在同一连通块，以及 v 是否已是 n 所在树中的相邻方向，利用各连通块大小和 Cayley 型补树总数分摊贡献。",
            "primary_topic": "树结构",
        },
        "2189E": {
            "statement_brief": "给二进制串 s，每次可把一个子串替换成其中出现次数不少于另一种字符的字符，操作代价为子串长度；求把整个串变成 1 的最小总代价，或判无解。",
            "transformed_statement": "把题目先看成：总代价等于 n-1 加操作次数，所以只需要判断最少需要几次合并操作。",
            "key_observations": [
                "每次把长度 L 的子串缩成 1 个字符，减少 L-1 个字符；总减少量固定为 n-1。",
                "只要串中有 1，就一定能在最多 4 次操作内完成。",
                "一次可行等价于全串 1 的数量不少于 0 的数量。",
                "二、三次可行分别由正/非负差值前后缀、整体差值为 -1、以及相邻 1 等局部条件刻画。",
            ],
            "solution_brief": "关键观察：优化代价其实是在最小化操作次数 k，因为总代价恒为 n-1+k。先排除全 0。然后按 k=0,1,2,3 的充要条件检查：全串已经是 1、全串差值非负、存在正差值前后缀或总差值为 -1、存在非负前后缀或连续两个 1；都不满足则答案对应 4 次。",
            "primary_topic": "构造与贪心",
        },
        "2180H2": {
            "statement_brief": "同时玩很多等差三元组游戏，本版本要求每次移动后公差不减。每个系列给出 x 的区间，问所有游戏合并后的先手胜负。",
            "transformed_statement": "把题目先看成：每个原游戏都可归一成状态 0<1<2≤x'，每步只能走到 x'-1 或 floor(x'/2)。",
            "key_observations": [
                "原始三元组按公差缩放后，只剩上界 x' 决定游戏状态。",
                "归一后的格兰迪数满足 g(x)=mex(g(x-1),g(floor(x/2)))。",
                "归纳可得 g(x)=0 当且仅当 x 的二进制末尾 0 个数为奇数，非零值在 1 和 2 间交替。",
                "区间里每个 x' 对应的原 x 数量可能在两端不同，要按奇偶贡献统计区间异或。",
            ],
            "solution_brief": "关键观察：条件版移动规则把游戏压成一维。对每个系列令 d=b-a，把 x 变为 floor((x-a)/d)，状态就是 0<1<2≤x'。格兰迪递推有二进制闭式：末尾 0 个数为奇数时为 0，否则按奇偶给 1 或 2。把 l..r 映射到 x' 区间后，只需统计各格兰迪值出现次数的奇偶，合并异或判断胜负。",
            "primary_topic": "博弈",
        },
        "2180E": {
            "statement_brief": "区间 [l,r] 上每个荷叶有一只青蛙，选择正整数 x 后所有青蛙从 i 跳到 i xor x；求有多少个 x 能让整个区间映射回自身。",
            "transformed_statement": "把题目先看成：要数区间在按位异或置换下的稳定子；不断去掉 l,r 共同的最高位，只处理跨越某个二进制半块的区间。",
            "key_observations": [
                "异或是双射，若 [l,r] 映到自身，则补集也会映到自身。",
                "[0,n) 能被多少个 x 保持不变，答案是 n 的最低位 1 对应的二次幂。",
                "若 l,r 同在同一个高位半块，减去共同高位不改变答案。",
                "跨半块时，区间外的左右两段要么各自保持，要么在全 1 掩码下镜像互换。",
            ],
            "solution_brief": "关键观察：先把问题规约到二进制块内。若区间端点最高位相同，统一去掉该位；跨过最高位边界后，把完整块分成左外段 A、中间目标段 B、右外段 C。因为异或是双射，B 稳定时 A∪C 也稳定，只可能是 A、C 各自稳定，或在全 1 掩码下对称互换。结合前缀区间 [0,n) 的答案 lowbit(n)，即可写出计数。",
            "primary_topic": "数论与同余",
        },
        "2161F": {
            "statement_brief": "给一棵树 T，任取点集 S 后构造完全图，边权为 T 上距离；求所有点集对应最小生成树权值之和。",
            "transformed_statement": "把题目先看成：对固定点集 S，最小生成树权值可以写成所有距离阈值下连通块数量的累加。",
            "key_observations": [
                "若只保留距离不超过 x 的完全图边，连通块数从 C(x-1) 降到 C(x) 时，正好需要那些权值为 x 的边。",
                "把树边细分后，从 S 中每个点同时向外扩张，连通块变化发生在多个方向第一次相遇的接触点。",
                "接触点可能是原树点，也可能在某条边内部。",
                "对随机点集统计每个接触点出现的概率，再乘回所有点集数量即可。",
            ],
            "solution_brief": "关键观察：最小生成树权值可由阈值连通块数求和，不必真的建完全图。把树看成可在半整数距离处相遇的细分树；点集中的点同时向外扩张，两个连通块第一次接触时贡献一次。分别枚举原顶点和边内部作为接触点，利用各方向最近被选点距离的分布统计概率，整体 O(n^2) 计算。",
            "primary_topic": "树结构",
        },
        "2138E2": {
            "statement_brief": "给非负整数 x，构造一个边长不超过 50、元素只为 -1/0/1、每行每列非零数不超过 3 且行列式等于 x 的方阵。",
            "transformed_statement": "把题目先看成：先构造一个稀疏矩阵模板，使行列式按一串相邻数递推变化；再为目标 x 找到一条长度不超过 50 的递减序列。",
            "key_observations": [
                "模板每扩一行一列，行列式会按类似相邻两项相减的规则更新。",
                "因此只要找到 A_m=x 和合适的 A_{m-1}，让反复取差能快速到达基础值，就能反向生成矩阵。",
                "斐波那契相邻数在这种减法过程中下降最慢，因此用斐波那契比例选 A_{m-1} 能控制长度。",
                "困难版用斐波那契展开或在黄金比例附近搜索，保证在给定值域内找到长度不超过 50 的序列。",
            ],
            "solution_brief": "关键观察：构造的核心不是随便填矩阵，而是控制行列式递推。题解使用一个每行每列最多 3 个非零的增量模板，使新增维度后行列式序列按相邻两项的差推进。于是问题变成：给 x 找一个前驱 y，使反复做较大数减较小数能在 50 步内到达基例。用斐波那契展开或黄金比例附近搜索找到 y，再按序列反向生成矩阵。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2128A": {
            "statement_brief": "有 n 袋垃圾，每秒必须先销毁一袋，若当时重量大于 c 要花 1 枚硬币；随后剩余袋子重量翻倍。求最少花费。",
            "transformed_statement": "把题目先看成：目标是尽量多地在变贵前免费销毁；每一秒都应优先销毁当前还能免费的最大袋。",
            "key_observations": [
                "只要还有免费袋，就没有理由先销毁昂贵袋。",
                "免费袋越重，留到下一秒越容易翻倍后变贵。",
                "因此每次取当前重量不超过 c 的最大袋销毁是最优的。",
                "排序后维护统一倍数即可模拟，不必真的每次乘所有袋子。",
            ],
            "solution_brief": "关键观察：免费机会是会过期的资源。每秒若存在重量不超过 c 的袋子，就销毁其中最大的，因为它最可能在下一次翻倍后变贵。无法免费时只能付费销毁。n 很小可直接模拟；排序并维护当前倍数也可以实现。",
            "primary_topic": "构造与贪心",
        },
        "2120E": {
            "statement_brief": "有 n 条车道，各有 a_i 辆车；每秒每条道过一辆车，车可换到任意车道末尾但额外增加 k 的不满值，求最小总不满值。",
            "transformed_statement": "把题目先看成：最终每条车道人数应被压到一个长度约为 k 的区间内；低于下界的道补车，高于上界的道挪车。",
            "key_observations": [
                "从长队尾部挪车到短队尾部才可能降低总等待。",
                "若最长队和最短队人数差不超过 k，再挪车只会被换道惩罚抵消。",
                "可以二分最终最小队长 v，比较把所有队补到 v 需要的车数和把超过 v+k 的车挪出数量。",
                "确定 v 后，只需微调边界上的若干车道，再计算等待和与换道惩罚。",
            ],
            "solution_brief": "关键观察：最终最优分布一定近似均衡，但允许最大和最小相差 k。二分下界 v：需要补到 v 的车数为缺口，超过 v+k 的车数为富余；若富余足够，就能把最小值抬到 v。确定 v 后，把数组夹到 [v,v+k]，再按剩余富余/缺口在两端微调，最后用每条道三角形等待和加换道次数*k 得到答案。",
            "primary_topic": "构造与贪心",
        },
        "2066E": {
            "statement_brief": "若干水桶中恰有一个桶外表带毒，天平只能比较重量，倒出某桶的水会触碰该桶而有风险；问能否保证找出毒桶且不触碰它。",
            "transformed_statement": "把题目先看成：相同初始重量的桶可先用天平判毒或判安全；安全桶里的水变成可自由使用的砝码资源。",
            "key_observations": [
                "若两个桶初始水量相同，天平不相等就能直接定位毒桶，相等则二者都安全。",
                "把非唯一重量桶的水集中到安全桶后，只剩重量两两不同的候选桶和一份可用水量 L。",
                "若候选桶重量不超过当前可用水量，或相邻候选桶差值不超过可用水量，就能验证并排除一个候选。",
                "只需检查前缀无法自动推进的特殊位置，因为每个特殊位置都会让前缀水量至少翻倍。",
            ],
            "solution_brief": "关键观察：先从相等重量桶得到安全水源。随后候选桶按重量排序，已确认安全的候选水量会加入可用水 L。能推进的条件是：下一个桶可被 L 补到某个参照重量，或某两个候选桶差值不超过 L。对于非特殊前缀总能自动推进；特殊前缀数量只有对数级，可用集合和线段树维护唯一重量、前缀和与后缀最小差来判定。",
            "primary_topic": "数据结构",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2066A": {
            "statement_brief": "交互题中已知数组 x，隐藏数组 y 满足 x_i!=y_i 且所有有序对不同。评测方二选一：要么是边 x_i->y_i 的有向图，要么是点 (x_i,y_i) 的集合；最多两次询问要判断是哪一种。",
            "transformed_statement": "把题目先看成：有向图查询可能返回不可达的 0，而平面曼哈顿距离在不同点之间一定为正；若 x 是排列，再用 x=1 和 x=n 的两个点做对称性区分。",
            "key_observations": [
                "若某个编号没有在 x 中出现，则图中从这个点出发没有边，询问它到任意其它点会得到 0。",
                "平面点之间不同坐标时曼哈顿距离不可能为 0，所以一次询问即可区分。",
                "若 x 是 1..n 的排列，找到 x_i=1 和 x_j=n 的两个下标。",
                "平面情况下两方向距离相同且至少 n-1；有向图不可能在 n 个点 n 条边中让双向最短路都达到这个长度。",
            ],
            "solution_brief": "关键观察：先找图模型独有的 0 回复。若 x 缺某个值 a，图中 a 没有出边，询问 a 到别点即可；平面模型不会返回 0。若 x 是排列，就询问 x=1 的点到 x=n 的点以及反向。曼哈顿距离会相等且至少 n-1，而有向图中这种双向极长距离不可能同时出现，据此判断。",
            "primary_topic": "交互",
        },
        "2064C": {
            "statement_brief": "数组非零，每次选一个数获得其绝对值；若选正数则删除它及其左侧前缀，若选负数则删除它及其右侧后缀。求最多金币。",
            "transformed_statement": "把题目先看成：任何时刻最优只会拿当前最左边的正数或当前最右边的负数，最终等价于选择一个分割点。",
            "key_observations": [
                "若要拿某个非最左的正数，先拿更左的正数不会更差，还能多得分。",
                "若要拿某个非最右的负数，先拿更右的负数同理不会更差。",
                "因此最终拿到的是某个前缀里的所有正数，加上某个后缀里的所有负数绝对值。",
                "枚举前后缀分界，用前缀正数和与后缀负数绝对值和取最大。",
            ],
            "solution_brief": "关键观察：可选位置其实会被边界支配。正数只需要考虑最左正数，负数只需要考虑最右负数。做若干次后，所有贡献一定形如“左边取正数、右边取负数”。预处理前缀正数和、后缀负数绝对值和，枚举分界求最大。",
            "primary_topic": "构造与贪心",
        },
        "2034H": {
            "statement_brief": "给一组互不相同的正整数，要求找出最大的整数线性无关子集；这里线性组合允许任意整数系数。",
            "transformed_statement": "把题目先看成：一个数是否能由其它数整数组合出来，由其它数的最大公约数是否整除它决定；再把条件转成若干质数幂的缺失证书。",
            "key_observations": [
                "由贝祖等式，若其它数的最大公约数整除 a_i，则 a_i 可由其它数整数组合得到。",
                "好集合要求每个 a_i 都缺少一个其它所有元素共有的质数幂因子。",
                "设这些证书质数幂乘积为 G，则第 i 个数应被 G/p_i^{q_i} 整除但不能被 G 整除。",
                "证书数量最多很小，可枚举质数幂集合，并用倍数计数数组检查是否存在对应元素。",
            ],
            "solution_brief": "关键观察：整数线性无关不是普通向量空间问题，而是最大公约数问题。集合好当且仅当对每个元素，其他元素的最大公约数不整除它。进一步可用互异质数幂作为每个元素的“缺失证书”：其它元素都有这个质数幂，自己没有。枚举小规模证书集合 G，用每个数的倍数出现次数判断能否选出对应元素。",
            "primary_topic": "数论与同余",
        },
        "2248F": {
            "statement_brief": "给矩阵和目标 k。一次操作可选任意子矩形全部减 1，要求最少操作后至少有 k 个格子成为峰值：该格不小于同行同列其它格子的总和。",
            "transformed_statement": "把题目先看成：对每个格子定义缺口 g=行和+列和-3*本格值，峰值条件就是 g≤0；一次操作对缺口的最大改善量可以统一界定。",
            "key_observations": [
                "当行列数都至少为 2 时，任意操作对任意格子的缺口最多减少 n+m-3。",
                "全矩阵减一能让所有格子的缺口同时达到这个最大下降速度。",
                "因此每个格子变峰值所需操作数独立可算，答案是第 k 小所需次数。",
                "单行或单列时只有全段、去左端、去右端三类操作有用，需要单独用不等式处理。",
            ],
            "solution_brief": "关键观察：峰值条件改写成缺口后，二维情形非常直接。若 n,m≥2，一次操作对任何格子的缺口改善不会超过 n+m-3，而全矩阵操作对所有格子同时达到这个上界，所以格子 (x,y) 的需求是 ceil(max(0,g)/(n+m-3))，取第 k 小。退化成一维时，只有全段和跳过一个端点的段可能最优，枚举端点策略解线性不等式。",
            "primary_topic": "构造与贪心",
        },
        "2247D2": {
            "statement_brief": "数组支持单点修改；每次要输出最小 k，使得只允许交换下标异或值不超过 k 的任意两项后，数组能排成非降。",
            "transformed_statement": "把题目先看成：当 k 是某个二次幂时，元素只能在固定长度的二进制块内任意重排；跨块顺序必须天然满足。",
            "key_observations": [
                "容易版结论：答案只可能是 0 或某个二次幂。",
                "允许异或不超过 2^j 的交换后，每个长度 2^{j+1} 的块内部可任意排列，但元素不能跨块。",
                "一个块能和右块拼成有序，只需检查左块最大值是否不超过右块最小值。",
                "困难版用线段树维护每个块的最小值、最大值和内部所需答案，合并时若左最大大于右最小，就把答案提高到半块长度。",
            ],
            "solution_brief": "关键观察：把下标异或限制看成二进制分块。补齐到二次幂长度后建线段树，每个节点代表一段固定块，维护段内最小值、最大值和把该段排好所需的最小 k。合并左右儿子时答案取两边最大；若左最大值大于右最小值，说明必须允许跨半区交换，于是还要和当前半段长度取最大。单点修改后沿树更新根答案。",
            "primary_topic": "数据结构",
        },
        "2247D1": {
            "statement_brief": "给数组，求最小 k，使得只允许交换满足 i xor j≤k 的下标对后，数组能被排成非降；本版本没有修改。",
            "transformed_statement": "把题目先看成：对每个候选二次幂限制，数组会被切成固定大小的块；块内可任意重排，块间不能交换。",
            "key_observations": [
                "任意非二次幂距离的交换可分解成若干个二次幂下标差的交换。",
                "因此最小答案只需考虑 0 或 2^j。",
                "若 k=2^j，所有元素都留在长度 2^{j+1} 的原块内。",
                "每个块内部排序后，全局有序当且仅当前一块最大值不超过后一块最小值。",
            ],
            "solution_brief": "关键观察：交换能力按最高不同位分块。对于 k=2^j，块大小为 2^{j+1}，块内通过若干合法交换可实现任意排列，但块之间无法交换。于是从小到大尝试 j，把每个块的最小最大值算出来，只要相邻块满足左最大≤右最小，就能排序。",
            "primary_topic": "构造与贪心",
        },
        "2234C": {
            "statement_brief": "环形连通容器之间的连通口高度为 h_i。对每个指定空容器 l，求在保持该容器为空时，其它容器最多能装多少总水量。",
            "transformed_statement": "把题目先看成：固定空容器 l 后，容器 i 的水位同时被从 l 顺时针到 i 和逆时针到 i 两条路径上的最高连通口限制。",
            "key_observations": [
                "若相邻两容器中较高水位超过连通口高度，则二者水位必须相等。",
                "从空容器向一侧推过去，任一位置水位不能超过沿途连通口高度的最大值。",
                "两侧都能把限制传到同一个容器，所以最大水位是两个方向限制的较小值。",
                "容易版可对每个 l 分别线性预处理两侧前缀最大。",
            ],
            "solution_brief": "关键观察：固定空点后，每个容器的上界是两条环上路径限制的交集。顺时针路径给出 max(h_l..h_{i-1})，逆时针路径给出另一侧最大值；把 w_i 取这两个上界的较小值即可同时满足所有连通条件。容易版直接对每个空点 O(n) 求和。",
            "primary_topic": "构造与贪心",
        },
        "2232B": {
            "statement_brief": "蛋糕每个位置有糖霜高度。把刀设在整数高度 h 从左到右扫，超出的糖霜会推到右侧。对每个前缀长度 i，求能让前 i 个位置最终齐平的最大高度。",
            "transformed_statement": "把题目先看成：前缀内部糖霜可以向右传递但不能从右向左补；因此答案受所有前缀平均值的最小值限制。",
            "key_observations": [
                "前 i 个位置若都至少为 h，则任意更短前缀的总糖霜也必须至少达到长度乘 h。",
                "所以 h 不可能超过每个前缀平均值的下取整。",
                "这个上界可以通过从左到右扫平达到。",
                "逐步维护累计和与当前最小平均值即可。",
            ],
            "solution_brief": "关键观察：能否把前 i 段齐平只由前缀总量约束决定。对任意 k≤i，前 k 个位置没有外部糖霜流入，所以高度 h 必须满足 k*h≤sum_{1..k}。最大 h 就是所有前缀平均值的最小下取整。扫描时维护累计和和答案最小值。",
            "primary_topic": "构造与贪心",
        },
        "2228E2": {
            "statement_brief": "数组中部分位置固定、部分为 -1。查询一段区间和总和 m，要求把 -1 填成非负数，计算所有合法填法下“前缀和平方和”的总和；还支持单点修改。",
            "transformed_statement": "把题目先看成：固定位置贡献、单个自由位置贡献和两个自由位置乘积贡献都能化成关于剩余和与自由个数的组合恒等式。",
            "key_observations": [
                "展开前缀和平方后，目标变成所有 i,j 的 b_i*b_j 乘一个位置权重。",
                "固定-固定、固定-自由、自由-自由三类贡献可分别计算。",
                "自由变量总和固定时，需要用插板法和若干 x、x^2、x^3 乘组合数的前缀求和公式。",
                "线段树节点维护这些可合并的统计量，查询区间后代入 m 得答案。",
            ],
            "solution_brief": "关键观察：先把 f(c)=Σ(prefix)^2 展开成二次型，而不是枚举填法。区间内已知总固定和、自由位置数后，合法填法总数由插板法给出；涉及一个自由变量、两个自由变量的期望式分别用 T0,T1,T2,T3 这类组合前缀和闭式计算。为支持修改和区间询问，在线段树里维护固定贡献、自由位置权重和跨项统计。",
            "primary_topic": "组合计数与概率",
        },
        "2217E": {
            "statement_brief": "给排列 p 和目标数组 d，要求构造另一个排列 q，使每个位置 i 被多少个 j>i 且 p_j>p_i 且 q_j>q_i 的位置支配，恰好等于 d_i。",
            "transformed_statement": "把题目先看成：按 p_i 从大到小插入位置，此时 p_j>p_i 的条件对已插入元素自动成立，只需控制下标更大的元素在 q 顺序中有多少排在 i 后面。",
            "key_observations": [
                "处理当前 i 时，已插入列表正好是所有 p 更大的位置。",
                "其中下标大于 i 的元素才可能支配 i。",
                "若这类元素数量 m 小于 d_i，则无解。",
                "把 i 插到列表中，使恰好 m-d_i 个下标更大的元素在它前面，就能保证剩下 d_i 个支配它。",
            ],
            "solution_brief": "关键观察：按 p 值降序处理后，支配条件少了一维。维护一个列表表示 q 从小到大的相对顺序。当前 i 只会被已处理且下标大于 i 的元素支配；设它们有 m 个，就把 i 插到恰好经过 m-d_i 个这类元素之后。最终列表位置即 q_i，若某步 d_i>m 则无解。",
            "primary_topic": "构造与贪心",
        },
        "2209A": {
            "statement_brief": "有若干怪物，当前战力 c 能击杀战力不超过 c 的怪物并增长 c；也可消耗拖鞋让某怪物战力加 1。求最终最大战力。",
            "transformed_statement": "把题目先看成：能杀就杀；拖鞋只应该用在已经弱于自己的怪物上，把它变强后再杀以换取更多战力。",
            "key_observations": [
                "最终一定不会故意放过可击杀怪物，因为击杀只会增加战力。",
                "若还有拖鞋且怪物战力小于 c，把拖鞋砸到它身上再击杀能净增收益。",
                "剩余可杀怪物中，按战力从小到大处理总是安全的。",
                "排序后逐个处理，能杀就先尽量使用拖鞋增强再杀。",
            ],
            "solution_brief": "关键观察：这题的顺序贪心很直接。把怪物战力排序，每次若当前最弱怪物不超过 c，就先用尽可能多但不超过 c-a_i 的拖鞋把它增强，再击杀获得更高 c；若最弱都杀不了，后面也杀不了，结束。",
            "primary_topic": "构造与贪心",
        },
        "2154D": {
            "statement_brief": "猫在树上从 1 出发，每条移动指令会让它任选一个相邻点；你还可以删除点但不能删掉猫所在点，且不能连续删除。构造不超过 3n 条指令，保证无论猫怎么走最后都到 n。",
            "transformed_statement": "把题目先看成：不断安全删除非 n 的叶子，树会缩小且不被分裂；最后只剩 n 时猫必在 n。",
            "key_observations": [
                "删除叶子不会把剩余树拆开。",
                "树按深度奇偶二染色，移动一次会让猫所在颜色翻转。",
                "若要删的叶子和猫可能所在颜色相同，就先移动一次；否则移动两次，确保猫不在该叶子上。",
                "每次删除前至少有一次移动，因此不会出现连续删除指令。",
            ],
            "solution_brief": "关键观察：用树的二分染色控制猫不在待删叶子。以 n 为根，维护当前叶子集合和猫可能所在颜色。每轮选择与当前颜色相反的叶子删除；若没有，就先发一次移动指令翻转颜色。删除后再发一次移动，更新颜色，并把新叶子加入集合。重复到只剩 n，猫无论怎么走都只能在 n。",
            "primary_topic": "树结构",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2081C": {
            "statement_brief": "给一个只含 0..3 的矩阵。一次可改任意格子的值，要求最后每一行、每一列的按位异或都为 0，求最少修改次数并构造方案。",
            "transformed_statement": "把题目先看成：每改一个格子，就同时修正一个行异或值和一个列异或值；目标是把非零行、非零列尽量配成异或为 0 的小组。",
            "key_observations": [
                "只需统计行异或值和列异或值分别等于 1、2、3 的数量。",
                "一次修改可以让某个非零行值和某个非零列值同时消失，前提是选择的新旧差值匹配。",
                "能凑出按位异或为 0 的二元组、三元组、四元组时，就能用同样数量的格子修改处理整组。",
                "按组数最大化先配二元组，再配三元组，剩余项用四元组兜底即可。",
            ],
            "solution_brief": "关键观察：矩阵本身不需要大规模搜索。先算所有行异或和列异或，非零值只有 1、2、3。修改格子等价于同时改变一个行状态和一个列状态，所以问题变成把这些非零状态分组，每组总异或为 0 且同时含行、列元素。尽量多组成小组，随后在对应行列交点处改值即可。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2078D": {
            "statement_brief": "有左右两条车道，依次经过若干对加法门或乘法门。每次门产生的新增人数可任意分到两侧，但已有人员不能换道，求最终总人数最大值。",
            "transformed_statement": "把题目先看成：新增的每个人应该被放到未来收益更高的一侧；从后往前算左右车道的一人边际价值。",
            "key_observations": [
                "当前已有人员不能换道，只有加法门和乘法门产生的新增人员能自由分配。",
                "若知道某一步之后左右各多 1 人最终能带来多少收益，当前新增人员全放到收益更高的一侧最优。",
                "加法门只产生固定新增人数；乘法门等价于额外产生 (倍数-1) 倍当前人数。",
                "从后往前维护左右边际价值，再正向累计人数即可。",
            ],
            "solution_brief": "关键观察：不要贪心看当前人数，而要看未来放大系数。倒序计算左右车道各 1 个新增人最终贡献的权重；遇到加法门时，这些新增人全部给权重更大的一侧，遇到乘法门时，它让当前人数额外产生若干人，这部分同样按更大权重计入。最后正向模拟或直接用倒序权重公式得到最大总人数。",
            "primary_topic": "构造与贪心",
        },
        "2049C": {
            "statement_brief": "有 n 个点成环，并额外连接 x 和 y。要求给每个点填非负整数，使每个点的值等于所有邻点值的最小未出现非负整数。",
            "transformed_statement": "把题目先看成：环上交替填 0、1 通常已经满足条件；只在奇环或额外边连接同值时需要放一个 2 打破冲突。",
            "key_observations": [
                "若一个点两侧邻居分别为 0 和 1，它的最小未出现值就是 2；若邻居只出现一种值，则可填另一种 0/1。",
                "从 x 开始沿环交替填 0、1，可以让大多数点自动满足最小未出现值条件。",
                "当 n 为奇数，或 x、y 奇偶性导致额外边两端同值时，会产生一个局部冲突。",
                "把 x 位置改成 2 后，额外边和相邻环边的最小未出现关系都能被修正。",
            ],
            "solution_brief": "关键观察：这不是复杂的图着色。先沿环从 x 开始交替填 0、1；如果环长为偶数且额外边连到异值，条件已满足。否则额外边或奇环会让某处邻居值集合缺失不对，把 x 改成 2 就能同时提供缺失值并消除冲突。",
            "primary_topic": "构造与贪心",
        },
        "2022B": {
            "statement_brief": "有若干车型库存 a_i，每个顾客最多买 x 辆车且每种车型最多买 1 辆，求卖完全部车至少需要多少顾客。",
            "transformed_statement": "把题目先看成：答案同时受单车型最大库存和所有车辆总量除以单人容量两个下界限制，而这两个下界合起来也足够。",
            "key_observations": [
                "同一车型每个顾客最多买一辆，所以顾客数至少是最大库存。",
                "每个顾客总共最多买 x 辆，所以顾客数至少是总库存对 x 的上取整。",
                "达到这两个下界后，可以把每种车型分散到不同顾客，再用剩余容量填满。",
                "因此答案就是两个下界的最大值。",
            ],
            "solution_brief": "关键观察：只看两个不可突破的容量限制。单一车型需要 max(a_i) 个不同顾客承接；所有车又需要 ceil(sum/x) 个顾客承接。若取二者最大值 K，则每种车型都能分配到 K 个顾客中的不同位置，总容量也足够，所以答案为 max(max(a_i), ceil(sum/x))。",
            "primary_topic": "构造与贪心",
        },
        "2222F": {
            "statement_brief": "原图的边权为 0..m-1，新图中两点颜色来自原图点，边权等于原图两点路径上缺失的最小边权；求让新图连通的最小总代价。",
            "transformed_statement": "把题目先看成：若忽略某个权值 w 后两点仍连通，那么它们路径缺失值不会超过 w；可以按边权分治维护这种首次连通关系。",
            "key_observations": [
                "新图边权的本质是原图两点路径边权集合的最小未出现值。",
                "代价 w 的候选连通性，可转成原图加入除 w 外的部分边后两点是否已经连通。",
                "用按权值分治和可撤销并查集，可以批量找出每对颜色第一次可连通的最小缺失权。",
                "得到这些候选边后，再按类似最小生成树的顺序选边让颜色图连通。",
            ],
            "solution_brief": "关键观察：不要显式建完整新图。两点新边代价是路径权值集合的最小未出现值；等价地，测试某个 w 时，把除 w 外的相关边加入并查集，看两端是否连通。题解用边权分治加可撤销并查集批量确定低代价连接，再对颜色层面的候选边做最小生成树。",
            "primary_topic": "图论与网络流",
        },
        "2175A": {
            "statement_brief": "无限长色带前 n 格已有颜色。之后第 i 格颜色等于当前色带中不同颜色数，问最终整条色带会出现多少种颜色。",
            "transformed_statement": "把题目先看成：设初始不同颜色数为 d；如果颜色 d 已经出现，过程立刻稳定，否则会依次补上 d、d+1、d+2。",
            "key_observations": [
                "下一格颜色只由当前不同颜色总数决定。",
                "若当前不同颜色数 d 已经是已有颜色，则再写 d 不会增加颜色数，过程稳定。",
                "若 d 没出现，写入 d 后不同颜色数变成 d+1，之后同理继续。",
                "最终会停在原数组中第一个不小于初始 d 的已有颜色处；若没有，就答案为 d 加补齐长度。",
            ],
            "solution_brief": "关键观察：整个无限过程只有一个数 d 在移动。先统计初始不同颜色数 d；若 d 已出现，则后面永远写 d，答案就是 d。否则会连续写入 d、d+1、...，直到遇到某个原本已经存在且不小于 d 的颜色值，写它时不再增加颜色种类。找这个最小已有颜色即可。",
            "primary_topic": "基础实现与模拟",
        },
        "2158C": {
            "statement_brief": "Alice 和 Bob 轮流选择位置，对 a_i 加上或减去 b_i；k 轮后按最大非空子段和计分，Alice 最大化、Bob 最小化，求最终分数。",
            "transformed_statement": "把题目先看成：偶数轮 Bob 能抵消 Alice 的一次选择；奇数轮只剩 Alice 最后一次有效加成需要最大化最大子段和。",
            "key_observations": [
                "当 k 为偶数，双方成对抵消，答案就是原数组最大子段和。",
                "当 k 为奇数，等价于 Alice 只选择一个位置 i 让 a_i 增加 b_i。",
                "若最优最大子段和经过 i，它等于以 i 结尾的最佳前缀加以 i 开头的最佳后缀再扣一次 a_i。",
                "预处理每个位置的最大子段前缀/后缀贡献，枚举 i 加上 b_i。",
            ],
            "solution_brief": "关键观察：博弈部分会被轮数奇偶消掉。偶数 k 时 Bob 可以把 Alice 的收益抵回原状，所以答案是原最大子段和。奇数 k 时只需考虑 Alice 最后把某个位置增加 b_i；预处理经过每个 i 的最佳子段和 L_i+R_i-a_i，再加上 b_i 取最大。",
            "primary_topic": "动态规划与状态设计",
        },
        "2122C": {
            "statement_brief": "给偶数个平面点，要把它们两两配对，使所有配对的曼哈顿距离总和最大。",
            "transformed_statement": "把题目先看成：一维最大配对是小半和大半相配；二维曼哈顿距离可同时按 x、y 的小半/大半分组。",
            "key_observations": [
                "在一维上，最大化绝对差总和时，应把较小的一半和较大的一半配对。",
                "曼哈顿距离是 x 方向差值加 y 方向差值，所以希望每对同时跨过 x 中位线和 y 中位线。",
                "按 x 小/大、y 小/大把点分成四类。",
                "左下配右上、左上配右下，就能同时最大化两维贡献。",
            ],
            "solution_brief": "关键观察：把二维拆成两个一维配对。先按 x 排序分成小半和大半，再按 y 排序分成小半和大半；每个点落入四个交集之一。为了让每对在 x 和 y 两个方向都跨半区，把左下与右上配、左上与右下配即可。",
            "primary_topic": "几何",
        },
        "2110B": {
            "statement_brief": "给一个合法括号串，机器人会删除一个左括号和一个右括号，问是否能让结果不再合法。",
            "transformed_statement": "把题目先看成：删除后总平衡仍为 0，所以只能通过让某个前缀平衡变成负数来破坏合法性。",
            "key_observations": [
                "删一个左括号和一个右括号不会改变最终总平衡。",
                "合法性被破坏只能是某个前缀平衡小于 0。",
                "最容易制造负前缀的做法是删最靠前的左括号和最靠后的右括号。",
                "若原串中间部分曾经回到平衡 0，则可以切断成两段并破坏；否则不行。",
            ],
            "solution_brief": "关键观察：总平衡始终为 0，所以只看前缀是否会变负。最强的删除方式是删第一个左括号和最后一个右括号；这等价于检查原串是否存在非末尾前缀平衡为 0。如果存在，删除后后半段开头会失去支撑而非法；否则任意删除都仍合法。",
            "primary_topic": "字符串",
        },
        "2109E": {
            "statement_brief": "给一个二进制串，要执行 k 次操作：每次选择一个当前为 0 的位置并翻转它前面的前缀；求合法操作序列数量。",
            "transformed_statement": "把题目先看成：从右往左决定每个位置被选多少次；当前位置当前值只由右侧已经做过的操作次数奇偶决定。",
            "key_observations": [
                "选择位置 i 只会影响 i 左边的位置，因此从右往左处理时，右侧状态已经固定。",
                "位置 i 当前是否为 0，由原字符和右侧操作次数奇偶共同决定。",
                "若在 i 处新增 c 次操作，需要把这些操作插入到已有操作序列中，组合数给出穿插方式。",
                "设 dp[i][j] 表示处理后缀 i..n 且已用 j 次操作的方案数，枚举 c 转移。",
            ],
            "solution_brief": "关键观察：前缀翻转题要反向看。处理到 i 时，所有右侧选择已经确定，因而 i 当前值只取决于右侧操作数奇偶。若它当前可被选择，就允许在 i 处放若干次操作；这些新操作与右侧 j 次操作的相对顺序用组合数统计。用后缀动态规划累计到 k 次即可。",
            "primary_topic": "动态规划与状态设计",
        },
        "2062F": {
            "statement_brief": "每个城市有两个参数 a_i,b_i，两城连边代价为 max(a_i+b_j,b_i+a_j)。对每个 k，求经过恰好 k 个城市的简单路径最小总代价。",
            "transformed_statement": "把题目先看成：令 x=(a+b)/2、y=(a-b)/2，边代价化为 x_i+x_j+|y_i-y_j|，路径贡献就能按端点和 y 排序处理。",
            "key_observations": [
                "代价变形后，路径中间点的 x 贡献出现两次，端点只出现一次。",
                "选定若干点后，y 的绝对值项在按 y 排序访问时最小，主要由端点极值决定。",
                "因此状态只需知道选了多少点以及当前选了几个端点。",
                "按 y 排序做动态规划，可同时维护各个 k 的最小路径代价。",
            ],
            "solution_brief": "关键观察：先做代数变形，把 max(a_i+b_j,b_i+a_j) 写成 x_i+x_j+|y_i-y_j|。这样一条路径的 x 部分只看点是端点还是中间点；y 部分在按 y 排列时由相邻差和端点决定。按 y 排序后做 DP，记录已选点数和端点数量，就能为每个 k 求最小值。",
            "primary_topic": "动态规划与状态设计",
        },
        "2053I2": {
            "statement_brief": "给数组 a，统计所有满足条件的数组 b 的价值和：a 是 b 的子序列、总和相同，并且 b 的最大子段和尽量小且长度尽量短。",
            "transformed_statement": "把题目先看成：先判定每个前缀能否在目标最大子段和限制下合法分段，再在困难版里给这些分段方案计数。",
            "key_observations": [
                "最优 b 的核心限制来自最大子段和；插入的数只能填在相邻 a 元素之间的空隙里。",
                "若某个空隙放多个数，可以合并或调整而不改善最优性，所以每个空隙最多保留一个有效插入数。",
                "容易版先做可行性动态规划，判断前缀能否以某个结尾状态达到最优限制。",
                "困难版在同一状态上增加计数，并用队列维护可转移区间，避免逐项枚举。",
            ],
            "solution_brief": "关键观察：先把“最小最大子段和、再最短长度”的字典序最优性转成分段限制。每个相邻空隙最多需要一个插入数，否则可以压缩而不变差。基于这个性质，容易版做前缀可行 DP；困难版在 DP 状态上累计不同 b 的价值贡献，并用队列维护同一段内可转移状态。",
            "primary_topic": "动态规划与状态设计",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2023B": {
            "statement_brief": "一场比赛按系统给题规则进行：解题得分，跳题会跳到 b_i 范围内尚未出现的最大编号题。求最终能获得的最大总分。",
            "transformed_statement": "把题目先看成：最终被访问过的题一定是某个前缀；与其最大化得分，不如最小化这个前缀里被跳过题目的扣分。",
            "key_observations": [
                "若 b_i≤i，跳过第 i 题永远不优，因为解掉它至少不亏且后续可达范围不差。",
                "若之前已经到过编号 j≥b_i 的题，当前跳题也没有额外价值。",
                "因此最优过程结束后，出现过的题形成 1..p 的前缀。",
                "把解题看成 0 代价走到 i-1，把跳题看成花 a_i 走到 b_i，问题变成最短路扣分。",
            ],
            "solution_brief": "关键观察：先证明答案只会落在某个题号前缀上。对前缀内题目，没拿到的分数就是跳题惩罚；从 i 解题可 0 代价到 i-1，跳题可花 a_i 到 b_i。建这个有向带权图，从 1 求到每个前缀端点的最小惩罚，再用前缀总分减惩罚取最大。",
            "primary_topic": "图论与网络流",
        },
        "2023A": {
            "statement_brief": "给 n 个长度为 2 的小数组，要按某个顺序拼成一个长数组，使逆序对数量尽量少，只需输出拼接顺序。",
            "transformed_statement": "把题目先看成：每个二元数组内部顺序不能变，两个相邻块的相对顺序只由各自元素和决定。",
            "key_observations": [
                "只需比较相邻两个块是否应该交换。",
                "若左块元素和大于右块元素和，交换这两个块不会增加逆序对。",
                "不断做这种相邻交换，最终得到按元素和非降排列的顺序。",
                "因此直接按每个二元组的和排序即可。",
            ],
            "solution_brief": "关键观察：用交换论证而不是计数逆序对。任意最优序列里，如果相邻两个二元组的元素和逆序，交换它们不会让总逆序对变多；反复交换后得到按和排序的方案，所以输出所有二元组按 a_i1+a_i2 非降排列即可。",
            "primary_topic": "构造与贪心",
        },
        "2245E": {
            "statement_brief": "树上两人轮流选择一条与上一条路径端点相交且不与旧路径共边的简单路径，不能走者输。问先手第一步选哪些路径能保证胜利。",
            "transformed_statement": "把题目先看成：先手第一条路径删掉后，后续路径都可以视为在剩余森林里自上而下延伸；局面胜负只看上一条路径上的剩余度数奇偶。",
            "key_observations": [
                "固定第一条路径后，把树在路径端点方向上定根，后续合法路径都会沿祖先到后代方向走。",
                "若上一条路径上的某个点在剩余森林中度数为奇数，当前玩家能走到另一个奇度点并把新路径全变偶。",
                "若上一条路径上的点全是偶度，任意走法都会给对手留下至少一个奇度点。",
                "所以先手第一步要让路径上所有点删边后的剩余度数全为偶数。",
            ],
            "solution_brief": "关键观察：第一步之后游戏有简单的奇偶判定。当前活动路径上只要存在剩余奇度点，就是胜态；从这个奇度点往下走到下一个奇度点，删掉路径后新活动路径全变偶。若全偶则任何行动都会制造奇度点给对手。于是统计先手第一条路径删掉后，路径上各点剩余度数是否全偶即可。",
            "primary_topic": "博弈",
        },
        "2210C2": {
            "statement_brief": "给数组 a 和上界 b_i，每个位置最多改一次且改成不等于原值的 1..b_i。要求所有子数组最大公约数不变，求最多能改多少位置。",
            "transformed_statement": "把题目先看成：为了保持所有子数组最大公约数，只需要守住相邻最大公约数；每个位置的最小可保留骨架是左右相邻最大公约数的最小公倍数。",
            "key_observations": [
                "若位置 i 能降低，最优先降到 lcm(gcd(a_i,a_{i-1}), gcd(a_i,a_{i+1}))。",
                "不能降低而只能增加的位置，新增倍数不能给左右最大公约数引入额外质因子。",
                "乘合数没有必要，只需考虑质数倍数。",
                "只枚举前 20 个质数就够，因为相邻相关乘积不可能同时覆盖这些质数。",
            ],
            "solution_brief": "关键观察：所有子数组最大公约数不变可压到相邻约束。对每个位置先算必须保留的骨架 c_i；能把 a_i 降到 c_i 就一定做。剩下只能把 c_i 乘一个不会污染左右最大公约数的质数，并且不超过 b_i。由于只需看前 20 个质数，做一维动态规划，状态记录当前位置选择不改或乘第几个质数，转移检查与左右相邻约束。",
            "primary_topic": "数论与同余",
        },
        "2180H1": {
            "statement_brief": "若干等差三元组游戏同时进行；每局给上界区间，玩家每步增加一个数并保持三数仍成等差数列，所有局合成取胜负，问先手是否赢。",
            "transformed_statement": "把题目先看成：每个上界 x 对应一局独立公平组合游戏；把等差三元组平移缩放后，状态只剩 q 和 d 的二进制因子次数。",
            "key_observations": [
                "不同局互不影响，可用格兰迪数按异或合并。",
                "把 (a,b,c,x) 平移为 (0,d,2d,y)，再令 d=2^kD、q=floor((y-2d)/D)，状态只依赖 (q,k)。",
                "递推可化为 g(q,k)=mex(g(q-2^k,k), g(q,k-1))，第三类转移可以删去。",
                "固定 k 时格兰迪序列以 2^(k+1) 为周期，因此区间异或可用周期前缀快速计算。",
            ],
            "solution_brief": "关键观察：难点是把每个区间里的大量上界压成周期格兰迪。先将一局规范化到 (q,k)，证明有效递推只含两个子状态，并且固定 k 的序列有 2^(k+1) 周期。于是每个 [l_i,r_i] 只需分成少量边界块和完整块，用前缀异或求该系列贡献，最后把所有系列异或起来判胜。",
            "primary_topic": "博弈",
        },
        "2153E": {
            "statement_brief": "定义 x! 在进制 k 下的末尾零数，并对 f_m(x,n) 取 2..m 中某个进制下两者末尾零较小值。求 x=1..n-1 的总和。",
            "transformed_statement": "把题目先看成：绝大多数 x 的答案为 0；只需要处理 n 附近、从最大不超过 n 的质数开始的一小段。",
            "key_observations": [
                "设 p0 是不超过 n 的最大质数，则所有 x<p0 都有 v_p0(x!)=0 而 v_p0(n!)>0，所以贡献为 0。",
                "在 n≤10^7 范围内，n 与前一个质数距离很小，只剩常数级 x 需要计算。",
                "复合进制 k 的最优贡献一定可由某个质数幂因子达到，所以只需枚举质数幂。",
                "还只需考虑会整除区间 [p0,n] 中某个数的质数。",
            ],
            "solution_brief": "关键观察：先用最大前驱质数把大部分 x 直接归零。剩余 x 都在 [p0,n]，数量由质数间隙控制。计算 f_m 时不用枚举所有 k，因为复合 k 的末尾零由其质因子幂的最小值决定，最优值会落到某个质数幂上。枚举相关质数及其不超过 m 的幂，计算阶乘中质因子次数并取最小。",
            "primary_topic": "数论与同余",
        },
        "2150E2": {
            "statement_brief": "交互题中数组里有一个值只出现一次，其它值出现两次；版本 2 要在更紧询问次数内找出这个唯一值。",
            "transformed_statement": "把题目先看成：先用版本 1 的递归缩小候选集，再用随机划分或洗牌二分，让每个候选平均花更少询问被排除。",
            "key_observations": [
                "版本 1 第一层递归后，候选值数量约为 n/4，已经可单独处理。",
                "随机把位置分成两半时，重复值有约一半概率两次都落在同一侧，可用较少询问排除。",
                "每个候选的平均询问数满足一个简单递推，整体期望可压到限制内。",
                "实际实现可先随机洗牌，再对候选做二分式检查，以控制最坏询问数。",
            ],
            "solution_brief": "关键观察：不是从零设计交互策略，而是在版本 1 之后优化候选排除成本。先递归到只剩约 n/4 个可能值；对每个候选，通过随机划分检查它是否在两边都出现，从而大概率快速排除重复值。进一步用洗牌后的二分检查替代纯随机，减少方差并保证询问数不超过限制。",
            "primary_topic": "交互",
        },
        "2140F": {
            "statement_brief": "数组上可反复选择 k 个位置，按选中和模 k 的结果让若干较小元素减 1。求数组和能降到的最小值，或判断可无限下降。",
            "transformed_statement": "把题目先看成：某个规模 k 的操作能降值，当且仅当数组中存在两个元素模 k 不同；若所有相关模数都一致，才会停止。",
            "key_observations": [
                "若任意 k 子集的和都被 k 整除，则任意两个元素必须模 k 同余。",
                "反过来，只要存在模 k 不同的两项，就能构造一次会下降的操作。",
                "一旦能在非最小元素间制造差异，就可以把过程转成无限下降。",
                "不能无限下降时，只需检查原数组和把最小值减 1 后是否仍满足所有同余停止条件。",
            ],
            "solution_brief": "关键观察：操作是否有效只取决于同余结构。对每个 k，若数组元素并非全同余，就存在可下降操作；多种情况会进一步导向无限下降。最终有限答案只可能是当前总和或当前总和减 1。实现时用 1..n-1 的最小公倍数合并同余条件；当该最小公倍数已超过值域时，等价于直接要求元素相等。",
            "primary_topic": "数论与同余",
        },
        "2138C1": {
            "statement_brief": "给一棵有根树，要给点标 0/1，且 0 的数量恰为 k。每个叶子的名字是根到叶的标签串，求所有叶子名字最长公共子序列长度的最大值。",
            "transformed_statement": "把题目先看成：答案上界是最浅叶深度 d；想达到 d，就必须能选出 d 层组，使每组统一标号且总 0 数可达。",
            "key_observations": [
                "最长公共子序列长度不可能超过最浅叶子的名字长度。",
                "若所有深度相同的点同属一组且同标号，则所有叶子能共享这一层字符。",
                "前 d 层按深度分组，组大小就是背包物品重量。",
                "若无法用这些组大小凑出 k 个 0，则答案至少还能做到 d-1。",
            ],
            "solution_brief": "关键观察：先抓住最大答案 d 的充要条件。为了让所有叶子有长度 d 的公共子序列，可以把每个深度层视为一组统一标号；于是是否能达到 d，变成这些组大小能否选若干个凑出 k。一般树中深度超过 d 的点可当作重量 1 的自由物品。做背包判断可达则输出 d，否则输出 d-1。",
            "primary_topic": "树结构",
        },
        "2133E": {
            "statement_brief": "树上隐藏一个会躲避检查并可移动的目标。可以检查点或切断某点所有边，要求构造不超过 floor(5n/4) 次操作保证抓到它。",
            "transformed_statement": "把题目先看成：先切掉少量关键点，把树分成若干条路径；路径上只靠从一端扫到另一端的检查就能抓住目标。",
            "key_observations": [
                "路径连通块可以用从一端到另一端的连续检查处理，检查过的前缀不可能再藏人。",
                "所有切边操作都可以提前做，因为提前限制移动不会让目标更容易逃。",
                "目标变成用不超过 n/4 个切点把树分成路径。",
                "树形染色把路径端点、中间点和切点分成三类；每个切点都能配到至少 3 个非切点。",
            ],
            "solution_brief": "关键观察：先把树改造成路径森林。切断操作可以全部放在最前面；切完后每条路径从一端扫过去即可。题解用树形染色决定切点：有三个以上端点型儿子或有中间型儿子的点设为切点，否则按端点/中间状态上传。每个切点可和至少三个其它点分组，所以切点数不超过 n/4，总操作数满足限制。",
            "primary_topic": "树结构",
        },
        "2127B": {
            "statement_brief": "一维格子里有墙和角色。每天对手先在空格建墙，角色再向左或右走：若该方向无墙则逃出，否则走到最近墙并摧毁它。双方最优，求逃出天数。",
            "transformed_statement": "把题目先看成：角色只关心左右最近墙的位置 L 和 R；每次选择一侧，就能保证下一次该侧边界至少向外推进一格。",
            "key_observations": [
                "若某侧没有墙，角色当天直接逃出。",
                "向左撞墙会摧毁左侧最近墙，所以下一轮左侧最近墙位置至少减 1；右侧同理至少加 1。",
                "对手每天只能补一面墙，最多阻止其中一侧推进过快。",
                "先手建墙后，答案由左右最近墙到边界的较小逃脱距离决定。",
            ],
            "solution_brief": "关键观察：状态不用记整串墙。设 L 是左侧最近墙、R 是右侧最近墙；轮到角色时，他能保证答案不超过 min(L+1, n-R+2)，对手也能通过补墙使推进速度不超过这个界。再考虑对手第一天能在角色两侧补一面墙，取让上述值最大的选择即可。",
            "primary_topic": "博弈",
        },
        "2122F": {
            "statement_brief": "给 n≤8 个颜色数量 a_i，要求构造一个顶点数不超过 333 的简单多边形，使三角剖分数量恰好等于对应多项式系数。",
            "transformed_statement": "把题目先看成：先构造能产生二项式系数数量的基础多边形，再用连接器把多个基础块的剖分数量相乘。",
            "key_observations": [
                "两条相邻线段分别放 a+1、b+1 个点时，三角剖分数量可以做成 C(a+b,b)。",
                "把基础形状扩展成矩形不会改变需要的剖分数量。",
                "用只有唯一剖分方式的三角连接器拼接多个块，整体剖分数相乘。",
                "直接连乘会用太多点；按颜色集合分治构造，可把点数降到 O(s log n)。",
            ],
            "solution_brief": "关键观察：把目标多项式系数拆成一串二项式系数，并用几何块实现乘法。基础块实现 C(a+b,b)，连接器只有一种剖分所以不改变乘法关系。为了不超顶点数，不按 a_1,a_2,... 线性累乘，而是把颜色集合二分：先选择前半颜色出现的位置，再递归构造两半，点数降到可接受范围。",
            "primary_topic": "几何",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2092E": {
            "statement_brief": "给 n×m 棋盘，部分格子已染黑白，其余格子任选黑白。要求相邻异色边数量为偶数，求合法补色方案数。",
            "transformed_statement": "把题目先看成：翻转一个内部格子会改变偶数条相邻边的异色状态，只有非角边界格子的颜色奇偶真正影响答案。",
            "key_observations": [
                "度数为偶数的格子翻色，只会让异色边数量奇偶保持不变。",
                "角点在边界环上也不影响最终判定，关键集合是非角边界格。",
                "沿棋盘边界走一圈，异色边变化次数必为偶数。",
                "因此合法条件等价于关键集合里黑格数量为偶数；若还有未定关键格，方案数直接减半。",
            ],
            "solution_brief": "关键观察：异色边数量的奇偶只由度数为奇数的格子决定，也就是非角边界格。若这些格子全已染色，就检查黑格奇偶，合法时其余空格任填；若其中至少一个未染色，则一半补色满足奇偶条件，答案是 2^(空格数-1)。",
            "primary_topic": "组合计数与概率",
        },
        "2085F2": {
            "statement_brief": "数组中 1..k 每种数至少出现一次，每次可交换相邻元素。求最少交换次数，使某个长度 k 的子数组恰好包含 1..k 各一次。",
            "transformed_statement": "把题目先看成：为每个值选一个出现位置，并把这些位置聚到一起；困难版可去掉“左右各选一半”的中位约束，用距离函数的变化量线性扫描。",
            "key_observations": [
                "对固定中心位置 p，每个值只需在 p 左右出现中选更近的一个。",
                "题解证明去掉左右数量正好各一半的限制后，最优值仍不会偏离真实答案。",
                "当 p 向右移动一格，某个值的最近贡献变化只会是 -1、0、1。",
                "贡献变化只在该值出现位置和相邻出现位置中点处改变，预处理差分后扫两遍即可。",
            ],
            "solution_brief": "关键观察：困难版的核心是把中位约束拿掉。枚举中心 p 时，对每个颜色选离 p 最近的出现位置，所得距离和仍能达到真实最优。每个颜色对 p 的贡献是分段线性函数，斜率只在出现点和相邻出现点中点改变。对所有颜色累加斜率差分，再做两次前缀，就能线性得到每个 p 的代价。",
            "primary_topic": "数据结构",
        },
        "2085F1": {
            "statement_brief": "数组中 1..k 每种数至少出现一次，每次可交换相邻元素。求最少交换次数，使某个长度 k 的子数组恰好包含 1..k 各一次。",
            "transformed_statement": "把题目先看成：先标记最终彩色子数组中的 k 个元素，再把这些标记元素向中间聚拢成连续段。",
            "key_observations": [
                "最优过程中没有必要交换两个都被选中的元素，只需把它们整体压成连续。",
                "被选元素向中位位置聚集时，相邻交换次数最小。",
                "固定中心 p 后，每个值要从 p 左边或右边选一个出现位置。",
                "容易版可枚举 p，并做小规模动态规划控制左右各选多少个值。",
            ],
            "solution_brief": "关键观察：相邻交换的代价就是把选中的 k 个位置压成连续段的距离代价，最佳聚集点在这些位置的中位附近。枚举中心位置 p，对每个值计算离 p 最近的左侧距离和右侧距离，再用动态规划选择哪些值从左边来、哪些从右边来，使左右数量满足连续段形状，最后减去固定内部距离常数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2059E1": {
            "statement_brief": "有 n 个长度为 m 的数组，操作会从某一行开始向后传递一个新元素并弹出每行末尾。给目标数组，求达到目标所需最少操作数。",
            "transformed_statement": "把题目先看成：原数组中未被弹掉的元素必须按原顺序形成一个前缀；枚举这个保留前缀长度并检查目标中能否容纳必要的新元素。",
            "key_observations": [
                "一次操作只会从末尾弹出旧元素，所以原有元素能保留的部分必须是某个前缀。",
                "若某个保留元素后面在目标中插入了新元素，它原来所在行的位置必须允许足够多次传递把它推到末端。",
                "对当前前缀，只需检查这些断点前面已有多少非前缀元素。",
                "枚举最大可保留前缀，答案就是总元素数减保留数量。",
            ],
            "solution_brief": "关键观察：不要模拟操作序列，先猜哪些原元素没被弹掉。保留元素一定是按原全局顺序的前缀。对目标数组扫描这个前缀，若某个保留元素后面接了外来元素，就要求它前面已有足够多外来元素把它推到可插入位置。逐个前缀维护这个条件，最大可行保留数决定最少操作数。",
            "primary_topic": "构造与贪心",
        },
        "2049B": {
            "statement_brief": "给一个由 p、s、点号组成的限制串，要求判断是否存在排列，使每个 p 位置前缀是对应长度的排列、每个 s 位置后缀是对应长度的排列。",
            "transformed_statement": "把题目先看成：首位的 s 和末位的 p 没有实际限制；去掉它们后，内部若同时存在 p 和 s 就矛盾。",
            "key_observations": [
                "完整数组本身就是排列，所以第 1 位的后缀限制和第 n 位的前缀限制可忽略。",
                "若只剩 p 限制，升序排列满足所有前缀限制。",
                "若只剩 s 限制，降序排列满足所有后缀限制。",
                "若内部同时有 p 和 s，较短限制段必须包含在较长限制段中，但端点缺失导致不可能。",
            ],
            "solution_brief": "关键观察：把边界无效限制先删掉。删掉首位 s、末位 p 后，如果非点字符只剩一种，就用升序或降序排列构造。若内部同时存在 p 和 s，则一个前缀段和一个后缀段都要求自己是完整排列，较短段会被迫包含在较长段里，但它们缺少不同端点，产生矛盾。",
            "primary_topic": "构造与贪心",
        },
        "2039E": {
            "statement_brief": "从数组 [0,1] 开始，每次把当前逆序对数量插入任意位置。给 n，求能得到多少个不同长度 n 数组。",
            "transformed_statement": "把题目先看成：一旦当前逆序对数量大于数组最大值，新插入的数会成为全局大数，之后状态只由数组长度和是否一直插到末尾决定。",
            "key_observations": [
                "当逆序对数 k 大于所有元素时，把 k 插到非末尾会让新的逆序对数继续变大，并保持同类状态。",
                "若把 k 插到末尾，逆序对数不变，可以连续插多次末尾。",
                "于是从长度 i 的稳定状态跳到更长状态，贡献只和第一次非末尾插入的位置数有关。",
                "可写出后缀和优化的一维递推，另外单独处理还没进入稳定状态的初始小长度。",
            ],
            "solution_brief": "关键观察：不要追踪整个数组。进入“逆序对数大于最大元素”的稳定区后，插到末尾不会改变逆序对数，插到其它位置会回到同类稳定区。设 f_i 为当前长度 i 处于稳定区时最终得到长度 n 数组的方案数，则 f_i=1+i*sum_{j>i} f_j，可用后缀和线性计算，再把初始 [0,1] 到稳定区的少数情况接上。",
            "primary_topic": "动态规划与状态设计",
        },
        "2247E": {
            "statement_brief": "构造一棵 n 点树，使按 1,2,...,n,1 依次相邻点的距离和等于 k；若无法做到则输出 -1。",
            "transformed_statement": "把题目先看成：以重心为根时，若相邻标签落在不同子树，距离就等于两个点深度之和；于是目标变成构造指定深度和并给子树交错贴标签。",
            "key_observations": [
                "距离和一定为偶数，且每条边在闭环游走中被跨过偶数次。",
                "以重心为根，距离和最多由两个大小接近一半的深子树达到，给出上界。",
                "先从星形树开始，再把叶子逐个下挂来把深度和一点点调到 k/2。",
                "贴标签时始终选剩余位置最多且不同于上一个标签所在的子树，保证相邻标签跨子树。",
            ],
            "solution_brief": "关键观察：先判 k 是否在偶数上下界内。构树时维护各重心子树大小不超过 n/2，从星形开始逐步把点挂深，使所有点深度和达到 k/2。随后给点编号：重心标 1，其余编号按最大剩余子树优先分配，避免相邻编号落在同一子树，这样 dist(i,i+1)=h_i+h_{i+1}，总和正好匹配。",
            "primary_topic": "构造与贪心",
        },
        "2246F": {
            "statement_brief": "给一个排列，每次可选相邻两项，把左项移到开头、右项移到末尾。要求用不超过 4n 次操作排序，或判断无解。",
            "transformed_statement": "把题目先看成：操作保持偶数 n 时的逆序奇偶性；只要奇偶允许，就可以从后缀逐个固定 1,2,...。",
            "key_observations": [
                "当 n 为偶数时，一次操作改变逆序对奇偶的次数为偶数，所以初始逆序为奇数则无解。",
                "维护后缀已经排好 1..x。",
                "若 x+1 不在首位，一次对它前一个位置操作即可把 x+1 放到后缀末端且不破坏旧后缀。",
                "若 x+1 在首位，用三次操作把它绕到末端；两个特殊轮转形态单独处理。",
            ],
            "solution_brief": "关键观察：可达性的唯一障碍是偶数长度下的逆序奇偶。可达时按后缀归位构造：假设 1..x 已在末尾排好，找到 x+1；若它不在首位，操作它前面的下标直接送到末尾；若在首位，用固定三步把它转出去再送到末尾。特殊循环排列按题解的短序列处理，总步数不超过 4n。",
            "primary_topic": "构造与贪心",
        },
        "2229C1": {
            "statement_brief": "数组元素非零。一次操作只能选择当前为正的位置 i，并把前缀 1..i 全部取相反数。容易版要求在不超过 n 次操作内让最终数组和最小。",
            "transformed_statement": "把题目先看成：最小和就是让所有元素都变成负数；从右往左扫，遇到当前为正的元素就翻它所在前缀。",
            "key_observations": [
                "选择位置 i 翻前缀不会影响 i 右边已经处理好的元素。",
                "从右往左维护当前前缀被翻过几次的奇偶即可知道 a_i 当前符号。",
                "若当前 a_i 为正，对 i 操作一次会把它变负，同时只影响还没处理的左侧。",
                "每个位置最多操作一次，所以操作数不超过 n。",
            ],
            "solution_brief": "关键观察：容易版没有必要做复杂优化，目标就是全负。倒序扫描数组，用一个翻转奇偶标记表示当前位置实际符号；如果实际值为正，就在该位置操作，记录答案并翻转奇偶。因为右侧不再受影响，最后所有数都是负数，数组和最小。",
            "primary_topic": "构造与贪心",
        },
        "2219B2": {
            "statement_brief": "交互题中长度 2n+1 的隐藏数组里，每个值出现两次，只有一个值出现三次。一次询问返回所选下标里只出现一次的值的数量，要求找出三次出现的位置。",
            "transformed_statement": "把题目先看成：对前缀询问可以得到一个由首次出现记 +1、第二次出现记 -1、第三次出现记 0 的序列前缀和。",
            "key_observations": [
                "询问前 k 个位置时，返回值等价于这个辅助序列的前缀和。",
                "三次出现的第三个位置会让前缀和奇偶变化模式暴露，可二分定位。",
                "找到第三次出现后，把数组循环重编号，让它变成新的开头。",
                "重复三次二分，就能依次得到第三、第二、第一次出现位置。",
            ],
            "solution_brief": "关键观察：询问不是直接查值，而是在查辅助前缀和。把每个值第一次出现记 +1，第二次出现记 -1，第三次出现记 0；前缀询问正好给这个和。利用前缀和奇偶可二分出三次出现中的最后一个位置，然后从这里循环移位重编号，再二分两次找到另外两个位置。",
            "primary_topic": "交互",
        },
        "2217G": {
            "statement_brief": "计数带 0/1 标签的二叉树。一次操作可翻转一条经过根的简单路径，代价是把全树清零所需最少操作数；给 n,k 求代价恰为 k 的树数。",
            "transformed_statement": "把题目先看成：把点标签换元为 x(v)=a(v) 异或左右儿子标签；根到点路径翻转只会切换终点的 x 值。",
            "key_observations": [
                "对固定树形，a 到 x 的映射是双射，可从叶到根恢复原标签。",
                "根到 u 的路径翻转只改变 x(u)，其它 x(v) 都不变。",
                "一个子树用根路径清零的次数就是其中 x(v)=1 的数量，因此标签计数只和子树大小有关。",
                "整棵树左右子树的操作可配对，总代价由左右所需次数最大值和根标签奇偶决定。",
            ],
            "solution_brief": "关键观察：先做标签变换，路径操作就从“翻一串标签”变成“只翻终点变量”。固定树形大小 m、子树代价 s 的标号数就是 C(m,s)。对根的左右子树，根路径可同时处理左右各一次，所以核心次数是 max(S_L,S_R)，根标签只决定是否额外加 1。于是代价恰为 k 可写成 max≤k 减 max≤k-2 的组合和，再用卡特兰数和二项式前缀和线性计算。",
            "primary_topic": "组合计数与概率",
        },
        "2201G": {
            "statement_brief": "在 n×n 的斑马图中选出一个点集，使其诱导子图是一条足够长的环，并输出该点集。",
            "transformed_statement": "把题目先看成：这是构造型启发式题；核心不是精确最优，而是设计能高密度重复、内部不产生额外边且能首尾连接的局部模块。",
            "key_observations": [
                "题目要求的 1/e 密度不是解法核心，官方构造目标约为 0.4 的密度。",
                "边由平方距离 13 决定，局部模式必须避免诱导出多余边。",
                "把一小块可延展形状当作模块，反复平铺并用连接段串起来。",
                "模块可以手工搜索，也可以把约束交给优化器寻找。",
            ],
            "solution_brief": "关键观察：这是少见的构造搜索题。不要从全图直接找大环，而是先设计一个“局部模块”：它在斑马图里像路径边一样可延展，内部没有额外环或冲突，并且能和相邻模块连接。把这个模块周期性铺开，可得到接近 0.4n^2 个点的诱导环，超过题目要求。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2201E": {
            "statement_brief": "给定只含 a、b、? 的偶长字符串 T。要求统计有多少个 a/b 字符串 S 与 T 的确定位置一致，并且能写成 A+B+B+A 的形式。",
            "transformed_statement": "把题目先看成：S 能写成 A+B+B+A，当且仅当前半段是后半段的一个循环位移；问题变成按周期统计两个半段能匹配的方案数。",
            "key_observations": [
                "A+B+B+A 的结构等价于把第二半段循环位移后与第一半段对齐。",
                "固定一个位移时，只要没有 a 与 b 冲突，重合的问号位置贡献 2 的幂。",
                "同一个周期串会在多个位移和多个周期长度里被重复计算。",
                "按最小周期长度分组，对约数关系做扣除：长度 d 的答案要从倍数长度里按倍数系数减掉。",
            ],
            "solution_brief": "关键观察：不要直接枚举 A、B，而是把 ABBA 结构变成两个半串的循环匹配。固定周期长度 d 后，把两半折叠成长度 d 的串，对每个循环位移计算无冲突且问号自由的位置数；这个匹配量可用卷积快速求。最后按约数从小到大扣掉更小最小周期带来的重复计数，累加各最小周期贡献。",
            "primary_topic": "字符串",
        },
        "2197B": {
            "statement_brief": "给排列 p 和数组 a。一次操作可以在相邻位置之间复制其中一个值到另一个位置，问 p 是否能通过若干次操作变成 a。",
            "transformed_statement": "把题目先看成：每个原始排列元素会扩张成一个连续段，操作只会改变相邻段长度，不会改变这些段在数组中的相对顺序。",
            "key_observations": [
                "复制相邻值等价于让某个原始元素占据的连续段扩大一格，另一个连续段缩小一格。",
                "这些连续段可以消失，但剩余段的左右顺序永远不能交换。",
                "因此目标数组从左到右出现的值，在原排列中的位置必须非递减。",
                "反过来，只要满足这个顺序条件，就能通过逐步扩张对应段构造出来。",
            ],
            "solution_brief": "关键观察：这题不是模拟复制次数，而是看顺序不变量。记录每个值在 p 中的位置，扫描 a，若这些位置不是非递减就不可能；若始终非递减，说明 a 只是把 p 的若干元素扩成连续块并删掉一些块，可以由相邻复制操作得到。",
            "primary_topic": "构造与贪心",
        },
        "2165B": {
            "statement_brief": "给一个多重集合 a。可以把它划分成若干非空多重集合，每份选一个众数放入结果多重集合 s，求不同 s 的数量。",
            "transformed_statement": "把题目先看成：若某些颜色不出现在 s 中，它们必须被 s 中颜色的出现次数“盖住”，因此只需统计被选颜色总容量是否足够。",
            "key_observations": [
                "没有被选进 s 的颜色 x，所有 x 都要藏在别的集合里，并且不能超过该集合选中众数的数量。",
                "一个被选颜色 c 最多提供 cnt_c 次遮盖能力，不管它在结果 s 中出现几次。",
                "可行条件等价于选中颜色的原出现次数总和至少达到全局最大出现次数。",
                "若选择颜色 c 进入 s，它在结果多重集合中的出现次数有 cnt_c 种选择，所以背包转移要乘 cnt_c。",
            ],
            "solution_brief": "关键观察：先别想怎么具体分组，只看没有进入 s 的颜色能不能被隐藏。选中颜色集合的总出现次数若小于某个未选颜色的出现次数，就不可能；反过来达到最大出现次数即可构造。于是对每个出现过的颜色做 0/1 背包，重量为 cnt_c，方案乘 cnt_c，最后把总重量不少于最大 cnt 的状态求和。",
            "primary_topic": "动态规划与状态设计",
        },
        "2164B": {
            "statement_brief": "给严格递增正整数序列，要求找两个元素 x<y，使 y 对 x 取模为偶数；若不存在则输出 -1。",
            "transformed_statement": "把题目先看成：偶数配偶数必然可行；剩下主要处理奇数之间何时能快速保证存在答案。",
            "key_observations": [
                "若有两个偶数，较大数对较小偶数取模一定是偶数。",
                "若只有一个偶数，直接枚举它与其它数的配对即可。",
                "对两个奇数 x<y，若 y<2x，则 y mod x=y-x，而奇数差为偶数。",
                "如果相邻奇数都不满足这个条件，奇数序列会至少翻倍增长，所以只需检查前 O(log V) 个候选。",
            ],
            "solution_brief": "关键观察：失败的奇数对会逼迫数值快速翻倍。先处理两个偶数和单个偶数的情况；对奇数按升序看，若相邻 y<2x 立即得到偶数余数。若一直没有，前若干项会按 2 倍增长，数量超过 logV 就矛盾；因此直接枚举小范围奇数对也能在线性乘小常数内找到答案或证明无解。",
            "primary_topic": "数论与同余",
        },
        "2155C": {
            "statement_brief": "一排巫师的斗篷可披在左侧或右侧。给出从每个位置看到的巫师数量数组 a，求有多少种斗篷朝向与该数组一致。",
            "transformed_statement": "把题目先看成：从位置 i 走到 i+1 时，只有第 i 个和第 i+1 个巫师的可见性会改变，所以相邻 a 值差分几乎决定了相邻斗篷关系。",
            "key_observations": [
                "移动一步时，远处巫师的可见状态不变，只需分析相邻两个巫师。",
                "因此任意相邻 a 值的差绝对值不能超过 1。",
                "给定第一个巫师朝向后，后续每个朝向都被相邻差分唯一确定。",
                "总共最多只有两个候选排列，分别枚举第一个朝向并整体验证即可。",
            ],
            "solution_brief": "关键观察：这题的核心是相邻差分约束，而不是搜索所有 2^n 种朝向。若某个 |a_{i+1}-a_i|>1 直接无解。否则分别假设第一个斗篷向左或向右，根据差分逐个推出后续朝向；最后重新模拟可见人数，两个候选中有几个匹配就输出几个。",
            "primary_topic": "构造与贪心",
        },
        "2138E1": {
            "statement_brief": "给非负整数 x，要求构造一个不超过 80 阶的方阵，元素只为 -1、0、1，且每行每列非零元不超过 3，使行列式等于 x。",
            "transformed_statement": "把题目先看成：把矩阵行列式解释成有向图的带权 cycle cover 求和，再构造一个恰有 x 条源汇路径的稀疏有向无环图。",
            "key_observations": [
                "行列式展开中的一个排列对应有向图里的一个 cycle cover。",
                "给无环图加上汇点到源点的边和中间点自环后，每个源到汇路径恰好对应一个 cycle cover。",
                "把原图边权设为 -1、自环和回边设为 1，排列符号与边权符号抵消，每条路径贡献都是 +1。",
                "于是问题变成构造一张出入度都很小、源汇路径数正好为 x 的 DAG；容易版可用三进制小模块串起来。",
            ],
            "solution_brief": "关键观察：不要直接凑矩阵，先凑路径数。构造一个 DAG，使源到汇的路径数为 x；再把 DAG 转成矩阵：DAG 边填 -1，中间点自环填 1，汇到源填 1。这样每个 cycle cover 都唯一对应一条源汇路径，且贡献为 +1，所以行列式就是路径数。用三进制 gadget 表示 x，可以在 80 阶和每行每列非零不超过 3 的限制内完成。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2122D": {
            "statement_brief": "给无向连通图。时刻 t 在点 u 时，要么等 1 秒，要么沿 u 的第 t mod deg(u)+1 条边走 1 秒；求从 1 到 n 的最短总时间，以及在最短时间下最少等待时间。",
            "transformed_statement": "把题目先看成：状态必须包含当前时间，因为可走边由时间模度数决定；关键是证明最短时间只需要算到 O(n)。",
            "key_observations": [
                "设 f(u,t) 为恰在时刻 t 到达 u 的最少等待秒数，可以做等待和移动两类转移。",
                "若已知最短到达时间 x，只需计算 t<=x 的状态。",
                "沿任意一条路径前进时，到每个点最多等 deg(u)-1 秒就能等到下一条目标边。",
                "取 1 到 n 的最短路，路径上没有跨越非相邻点的边，且外部点不可能连到路径上 4 个及以上点，因此这条路径度数和不超过 3n。",
            ],
            "solution_brief": "关键观察：难点不是 DP，而是把时间上界压住。做最短时间层的 DP，状态为点和时间，值为最少等待。为了证明只算到 3n 足够，取一条边数最少的 1 到 n 路径；它没有弦，路径外每个点最多邻接路径上 3 个点，所以路径顶点度数和 ≤3n。沿这条路径最坏也能在这些度数和时间内走完，因此 DP 到 3n 即可。",
            "primary_topic": "图论与网络流",
        },
        "2120G": {
            "statement_brief": "给一张已有欧拉迹且不是简单路径的连通无向图 G 和整数 k，判断第 k 次迭代线图 L^k(G) 是否仍有欧拉迹。",
            "transformed_statement": "把题目先看成：线图中的一个点对应原图一条边 uv，它的度数是 deg(u)+deg(v)-2，所以欧拉性可以在原图度数奇偶和少量结构上判断。",
            "key_observations": [
                "若当前图所有点度数为偶数，则它的线图也全为偶度，之后一直有欧拉回路。",
                "线图顶点的奇偶只取决于原边两端度数奇偶是否不同。",
                "真正麻烦的是原图只有两个奇点时，迭代一两次可能改变欧拉迹存在性。",
                "这些特殊情况可用原图结构判断：看奇点、删去奇点后的连通块，以及度数为 1 或 2 的尾路径长度。",
            ],
            "solution_brief": "关键观察：不要显式建 L(G)。对原图边 uv，在线图里的度数为 deg(u)+deg(v)-2，因此下一层有多少奇点可以直接由原图边两端奇偶算出。若进入全偶图，后续都为 YES；若处在两个奇点的边界情况，就检查奇点之间、删奇点后的块结构，以及由度数 1/2 点组成的尾路径在每次取线图时会缩短 1 的事实。所有判断都能在原图上 O(n+m) 完成。",
            "primary_topic": "图论与网络流",
        },
        "2101A": {
            "statement_brief": "把 0 到 n^2-1 放进 n×n 网格，要求最大化所有子矩形的 MEX 之和。",
            "transformed_statement": "把题目先看成：总 MEX 和等于对每个 k，统计有多少子矩形同时包含 0..k-1；所以低值前缀的包围矩形越居中、越接近正方形越好。",
            "key_observations": [
                "不含 0 的子矩形贡献为 0，因此 0 应放在最中心。",
                "MEX 至少为 k 等价于子矩形包含所有 0..k-1。",
                "固定已放低值集合的包围矩形，包含它的子矩形数量由上下左右可扩展距离相乘决定。",
                "同面积下，包围矩形越接近正方形且越居中，被包含次数越大。",
            ],
            "solution_brief": "关键观察：优化 MEX 和就是让每个低值前缀被尽可能多的子矩形包含。按从小到大放数，始终让 0..k 的包围框保持居中且尽量接近正方形即可；从中心向外螺旋填数正好满足这个性质，因此直接输出中心螺旋排列。",
            "primary_topic": "构造与贪心",
        },
        "2084G2": {
            "statement_brief": "给部分缺失的排列，需要补全后最大化所有子数组博弈值 f 的总和；困难版要求在线性对数复杂度内完成。",
            "transformed_statement": "把题目先看成：子数组博弈值只由两端点和长度奇偶决定，随后转成在数轴上给点染黑白，使异色点对距离和最小。",
            "key_observations": [
                "容易版先证明 f(c) 只取决于 c 的两个端点：长度奇偶决定取两端的较大值还是较小值。",
                "总贡献可化为常数减去所有奇偶位置异色值对的距离和。",
                "补全排列等价于给数轴上的未定点染黑白，并控制黑点数量。",
                "DP 数组关于黑点数量是凸的；维护相邻差分后，每步只剩加线性函数、整体平移和插入 0。",
            ],
            "solution_brief": "关键观察：先把博弈完全消掉。根据端点公式，最大化总 beauty 等价于最小化不同颜色点对的距离和；固定前 i 个值、选 j 个黑点的 DP 是凸的。困难版不直接存 f(i,j)，而存差分 g(j)=f(j+1)-f(j)。每轮更新只会给 g 加线性函数、右移、插入一个 0 并保持有序，用 Treap 懒标记维护这些线性变换即可。",
            "primary_topic": "数据结构",
        },
        "2084F": {
            "statement_brief": "给排列 a 和带空位的排列 c。要补全 c 得到排列 b，使 a 能通过至多 n 次指定的最小值右循环操作变成 b；无解输出 -1。",
            "transformed_statement": "把题目先看成：这种操作不会把 a 中已经按值顺序保持的有序对变成逆序，所以 b 必须保持 a 中的偏序关系。",
            "key_observations": [
                "一个排列 b 可达，当且仅当 a 中所有有序对在 b 中仍保持同样先后顺序。",
                "必要性来自操作不会制造这类逆序；充分性可从左到右把 b_i 拉到当前位置。",
                "已填位置若违反偏序直接无解。",
                "未填数字在 c 中都有一个可放区间 [l_x,r_x]；这些区间之间天然满足与 a 中顺序一致的单调性。",
            ],
            "solution_brief": "关键观察：把复杂操作替换成偏序约束。先按 a 中位置定义必须保持的相对顺序，检查 c 中已给数字是否冲突。对未给数字，根据已给数字推出它在 c 中可放的区间。然后从左到右填空，每次选择 l_x 已到达且 r_x 最小的数字；若 r 相同取较小值。由于区间端点随 a 中顺序单调，这个普通区间贪心同时保证互相偏序合法。",
            "primary_topic": "构造与贪心",
        },
        "2081B": {
            "statement_brief": "给相邻元素均不相等的数组。一次操作可重写一段，但必须保留该段内部每对相邻元素的大小关系；求最少几次能让全数组严格递增。",
            "transformed_statement": "把题目先看成：只关心相邻逆序对数量。一次重写一段最多只能改变段两端与外界的比较，因此最多消掉两个逆序对。",
            "key_observations": [
                "段内部比较模式不能改，能改变的只有左边界和右边界两处相邻关系。",
                "若当前有 s 个逆序对，答案下界是 ceil(s/2)。",
                "当 s 为奇数或 s 为 0 时，这个下界可以达到。",
                "当 s 为正偶数时，想每次消两个逆序，第一处逆序左端和最后一处逆序右端之间必须能容纳严格递增序列，即 a[p2]-a[p1] >= p2-p1。",
            ],
            "solution_brief": "关键观察：先数相邻下降边。每次操作最多修两个下降边，所以答案至少为 ceil(s/2)。若 s 是奇数，最后一次只修一个即可；若 s 是正偶数，要达到 s/2 次就要求所有操作都修两个边，这会把中间整段夹在第一处逆序左端 p1 和最后一处逆序右端 p2 之间。只有 a[p2]-a[p1] >= p2-p1 时能塞下严格递增序列，否则多一次操作。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2066D2": {
            "statement_brief": "有 n 层楼、每层一人，总共记录了 m 次纸飞机发射者，其中一些发射者缺失。每层住户视角下最终至少看到 c 架飞机，且看到够 c 架后不会再发射，求补全记录的方案数。",
            "transformed_statement": "把题目先看成：数字 i 的所有出现位置只能落在前 c 加上更小楼层已出现次数的前缀内；已有非零记录只是在这些位置上提前占坑。",
            "key_observations": [
                "第 i 层只有在自己视角还没看到 c 架时才会发射，所以忽略更小编号后，i 只能出现在前 c 个可用位置里。",
                "若 cnt_i 是数字 i 的总出现次数，那么 i 的所有位置必须在前 c+cnt_1+...+cnt_{i-1} 个位置内。",
                "困难版已有非零数字会占据位置；转移时要扣掉前缀中已经固定的大于等于当前数字的坑。",
                "状态只需记录已经安排到哪个数字，以及目前总共安排了多少个元素。",
            ],
            "solution_brief": "关键观察：把可信记录条件改写成“每个楼层编号的出现位置上界”。设 dp[el][sum] 表示已安排 1..el 且总出现次数为 sum 的方案。枚举当前数字放 k 个，它们必须全部落在前 c+sum-k 个位置；同时 k 要覆盖原记录中已固定的 el，且前缀里被更大固定数字占掉的位置不能再用。剩余空位中组合选择 k-cnt[el] 个位置，乘上 dp[el-1][sum-k]，答案为 dp[n][m]。",
            "primary_topic": "动态规划与状态设计",
        },
        "2027B": {
            "statement_brief": "定义可脆弱数组：能对若干子数组执行 Stalin Sort，最终变成非递增。给数组 a，求最少删除多少元素能让它可脆弱。",
            "transformed_statement": "把题目先看成：一个数组可脆弱当且仅当首元素是全局最大值；因此要保留一个以某位置开头、后面元素都不大于它的最长子序列。",
            "key_observations": [
                "若首元素是最大值，对整个数组执行一次 Stalin Sort 就能得到非递增序列。",
                "若最大值不在首位，任何子数组 Stalin Sort 都不会删除全局最大值，也不会删除当前首元素。",
                "因此首元素不是最大值时，最终不可能变成非递增。",
                "枚举保留子序列的第一个元素，后面只能保留不大于它的元素。",
            ],
            "solution_brief": "关键观察：别模拟多次 Stalin Sort，直接抓住首元素最大这个充要条件。枚举原数组中哪个元素作为删除后的首元素，保留它以及右侧所有不大于它的元素，得到一个可脆弱子序列；取最大保留长度，答案就是 n 减去这个长度。",
            "primary_topic": "构造与贪心",
        },
        "2021D": {
            "statement_brief": "每天必须选择一个连续饮料区间销售；从第二天起，新区间必须和前一天有交集，也必须包含前一天没卖过的饮料。给每天每种饮料利润，求最大总利润。",
            "transformed_statement": "把题目先看成：每天选区间等价于选两条边界；相邻两天合法等价于新区间严格包含前一天左端点或右端点之一。",
            "key_observations": [
                "一行里选饮料 l+1..r，利润就是前缀和 pref[r]-pref[l]。",
                "新区间既要碰到旧区间又要走出旧区间，只需严格跨过旧区间的某个端点。",
                "因此转移时不必记完整旧区间，只需分别维护“旧左端点为 p”和“旧右端点为 p”的最优值。",
                "固定新右端点 r 时，枚举 l<p<r 的最大值可以用前缀最大分三步求出；新左端点对称用后缀最大。",
            ],
            "solution_brief": "关键观察：把区间换成边界后，合法转移只是在新区间内部包含一个旧端点。维护 dpL[p]、dpR[p] 表示上一天某个端点在 p 的最优利润。处理新一行时，用前缀和表示新区间利润，并用前缀最大快速求所有 l<p<r 的 max(dp[p]-pref[l])+pref[r]；左端点版本对称处理。每行 O(m)，总复杂度 O(nm)。",
            "primary_topic": "动态规划与状态设计",
        },
        "2246C": {
            "statement_brief": "给非降数组 a，元素可能为 -1 或正整数。统计有多少个下标子序列的交错和为 0，答案取模。",
            "transformed_statement": "把题目先看成：由于数组非降，正数部分交错和为 0 基本等价于每个相等值选偶数个；出现 -1 时再按 -1 的选择奇偶分类。",
            "key_observations": [
                "若只含正数，交错和为 0 必须且只需每个相等值组选偶数个。",
                "一个大小为 s 的值组，选偶数个和选奇数个的方案数都为 2^(s-1)。",
                "没有 -1 时答案为 2^(n-d)，其中 d 是不同正数个数。",
                "若选奇数个 -1，正数部分交错和必须为 -1，这只会发生在某对相邻值 v、v+1 被选奇数次，其余组选偶数次。",
            ],
            "solution_brief": "关键观察：利用非降顺序把交错和按相邻两项配对。正数情况下，每个差值项都非正，要和为 0 就只能每对相等，因此每个值组选偶数个。若存在 -1，先数选偶数个 -1 的基础贡献；选奇数个 -1 时，需要正数部分补出 -1，等价于恰好挑一对相邻值 v 和 v+1 作为奇数组。最终答案是基础 2^(n-d) 乘以可选相邻值对数量加一。",
            "primary_topic": "组合计数与概率",
        },
        "2234D": {
            "statement_brief": "给首尾两个 n 位二进制数。中间数按二分过程不断由两端异或填入，最后要求所有位置的置位数乘零位数之和。",
            "transformed_statement": "把题目先看成：整个序列只会出现 A、B、A xor B 三种数，而且位置下标模 3 决定是哪一种。",
            "key_observations": [
                "设首数为 A、尾数为 B、C=A xor B；任意一次异或都只会在 A、B、C 三者之间轮换。",
                "A xor B=C，B xor C=A，C xor A=B，所以归纳后不会产生第四种数。",
                "可以把 A、B、C 分别对应到三个不同的下标模 3 余数。",
                "二分填入的中点模 3 一定是两个端点余数之外的第三类，因此对应关系保持不变。",
            ],
            "solution_brief": "关键观察：不要真的生成 2^k+1 个数。序列值只有 A、B、C=A xor B 三种，并且可用下标对 3 取模确定。先根据 k 判断首尾和中点分别对应哪个模 3 类，计算 1..2^k+1 中三类下标数量，再分别乘上 A、B、C 的 popcount 与零位数贡献即可。",
            "primary_topic": "数论与同余",
        },
        "2165A": {
            "statement_brief": "环上有 n 个数。每次合并相邻两数，合并后值为较大者，代价也是较大者；求合并成一个数的最小总代价。",
            "transformed_statement": "把题目先看成：最小元素总可以先并到较小邻居里，反复执行这个贪心；等价公式是所有相邻边最大值之和减去全局最大值。",
            "key_observations": [
                "任意合并序列里，当前最小元素迟早要并入某个不小于它的邻居。",
                "把这次合并提前做不会让之后代价变差，因此可反复合并当前局部最小。",
                "从全局最大值处断环后，序列上每个元素最终向左或向右被更大元素吞掉。",
                "每条相邻边贡献两端较大值；环上全局最大值会被多算一次，最后减掉它。",
            ],
            "solution_brief": "关键观察：贪心正确性来自“最小值提前合并不吃亏”。不断把当前最小元素并入较小邻居，最终总代价可整理成闭式：sum max(a_i,a_{i+1}) - max(a_i)，其中 a_{n+1}=a_1。实现时直接扫一圈求相邻较大值之和再减全局最大即可。",
            "primary_topic": "构造与贪心",
        },
        "2157F": {
            "statement_brief": "不知道初始技能 s，只知道 1<=s<=n。要输出一串任务，使任意初始 s 最终都至少到 n，且总费用不超过 10^6。",
            "transformed_statement": "把题目先看成：维护所有可能技能值的集合；选择难度 y 后，最佳时长就是把 y 跳到集合里下一个已存在位置，从而合并可能状态。",
            "key_observations": [
                "对固定任务难度 y，最优时长 l 是最小的、使 y+l 已在可能技能集合中的值。",
                "按 1,2,... 或 n-1,n-2,... 的朴素顺序都会导致费用太大。",
                "可以分层把技能值按模数归并：先固定模 2，再模 4，或推广到模 m。",
                "模数 m 越大层数越少，但每层上升难度次数越多；平衡 n 和 1000m 后取 m 约为 n 的三次方根。",
            ],
            "solution_brief": "关键观察：这是构造一个“压缩所有可能技能状态”的策略。把操作只看成选 y，因为最优 l 可由当前可能集合决定。按模 m 分层处理：每一层把同余类内的状态向更高值合并，层数约 log_m n，每层普通成本约 n，跨同余块的上升难度额外花 1000。取 m≈三次方根 n，可把总费用压进预算。",
            "primary_topic": "构造与贪心",
        },
        "2147I2": {
            "statement_brief": "构造长度为 n 的序列，使相邻差绝对值严格递增，并且不同取值不超过 m；困难版要用很少的不同点走出很多步。",
            "transformed_statement": "把题目先看成：把已有构造里的每个点膨胀成一个小簇，再用少量枢轴点把一次旧跳跃替换成很多次更长的新跳跃。",
            "key_observations": [
                "两个相隔足够远的点簇，加上两个标准枢轴点，可以在两个簇之间来回产生约 4t 次递增跳跃。",
                "若起点不是簇的端点，再加一个方向枢轴就能在簇内调整位置。",
                "因此一个 m' 点、g(m') 跳的构造，可膨胀成 tm'+3g(m') 个点、约 (4t-2)g(m') 跳的新构造。",
                "用 DP 选择每次膨胀参数 t 和 m'，再递归恢复具体点坐标。",
            ],
            "solution_brief": "关键观察：不要一次性手造 30 万步，而是递归放大短构造。把旧构造每个点替换成距离很小的 t 点簇，旧的每条跳跃用远距离簇间跳跃和 2 到 3 个枢轴点展开成一串严格变长的跳。先用 DP 算出给定 m 能产生的最大跳数和转移参数，再递归构造坐标；小 m 的基础构造用预处理补足。",
            "primary_topic": "构造与贪心",
        },
        "2140D": {
            "statement_brief": "给 n 条线段。每次取两条未标记线段，各选一点形成一条新标记线段；原线段也标记。求最终所有标记线段长度和最大值。",
            "transformed_statement": "把题目先看成：原线段长度固定，只需决定每条线段在配对新线段中贡献左端点还是右端点。",
            "key_observations": [
                "为了让新线段最长，左侧点应取某条线段左端，右侧点应取另一条线段右端。",
                "偶数 n 时，恰好 n/2 条线段贡献右端点，n/2 条线段贡献左端点。",
                "最大化等价于从 sum r_i 中减去 n/2 个最小的 l_i+r_i。",
                "这种选择可以调整成合法配对；若 n 为奇数，枚举或公式处理一个未配对线段。",
            ],
            "solution_brief": "关键观察：配对细节可以先放一边，目标值只取决于哪些线段拿左端、哪些拿右端。偶数 n 时初始化答案为所有 r_i 之和，再选 n/2 条线段改成贡献 -l_i，这相当于减去它们的 l_i+r_i，所以选最小的 n/2 个。奇数 n 时留一条线段不参与新线段贡献，对每个可能留出的线段取偶数情形最大值，或用排序后位置关系 O(1) 处理。",
            "primary_topic": "构造与贪心",
        },
        "2138D": {
            "statement_brief": "一维轨道上有 n 个保持相对顺序的滑块，给 q 个把第 i 个滑块移到 x 的操作。操作顺序遗失，需要对所有操作排列下的最终滑块位置求和。",
            "transformed_statement": "把题目先看成：令 b_i=a_i-i 消掉滑块占位，移动会变成对左侧取 min、对右侧取 max，并且 b 始终非降。",
            "key_observations": [
                "把位置减去编号后，滑块互相推挤的效果可以在非降数组 b 上表达。",
                "一次把第 i 个滑块设到 x，等价于 b_i 赋值，同时左边被 min 限制、右边被 max 限制。",
                "固定一个滑块和最终值 b_e，只需关心每个操作参数相对 b_e 是小于、等于还是大于。",
                "最终把 b_i 设成 b_e 的最后有效操作必须是参数等于 b_e 的那次；其它无效操作可任意插入，用组合/逆元统计贡献。",
            ],
            "solution_brief": "关键观察：先用 b_i=a_i-i 把“推开相邻滑块”变成单调数组上的 min/max/赋值操作。对每个滑块单独求期望式贡献：枚举哪个操作最后把它定到某个值 b_e，参数在 b_e 两侧的操作只负责保证此前状态小于或大于 b_e，真正无影响的操作可插在任意位置。把所有操作按参数排序后维护左右计数，就能对每个滑块累计所有排列下最终位置之和。",
            "primary_topic": "组合计数与概率",
        },
        "2115F2": {
            "statement_brief": "维护 n 个集合，在线执行前缀插入、前缀翻转、删除某元素，并在每次操作后询问某个集合的最小元素；困难版规模为 3e5。",
            "transformed_statement": "把题目先看成：前缀操作作用在集合序列上，用可持久化平衡树维护序列；每个树节点挂一个“整段集合都包含这些元素”的懒集合。",
            "key_observations": [
                "前缀插入可以把序列 split 出前缀，在对应子树根上挂一个元素。",
                "前缀翻转只是平衡树区间翻转懒标记。",
                "每个插入元素只存在于某一个节点的直接集合 T 中，删除时可以直接定位并移除。",
                "查询叶子集合时沿持久化父关系递归找非空懒集合；空的旧版本节点可以被清理，摊还复杂度受持久化节点数控制。",
            ],
            "solution_brief": "关键观察：不能真的把一个元素插进前 r 个集合。用带叶子的可持久化平衡树表示集合序列，每个内部节点记录“整棵子树所有叶子都含有”的元素集合，并把大集合拆成本节点直接集合 T 和若干子节点来源。split/merge/reverse 都只改树结构和懒标记；插入只挂到前缀根，删除只从元素所在的 T 中删。查询某个叶子时递归合并它祖先来源里的最小未删元素，空旧节点被摊还删除。",
            "primary_topic": "数据结构",
        },
        "2115A": {
            "statement_brief": "给正整数数组。一次操作选 i、j，把 a_i 改成 gcd(a_i,a_j)。求让所有元素相等的最少操作次数。",
            "transformed_statement": "把题目先看成：最终所有数只能变成全局 gcd。若数组里已有 gcd，直接用它把其它数改掉；否则先最少步造出一个 gcd。",
            "key_observations": [
                "操作只会把某个元素变成原值的因子，所以最终公共值必须整除所有初始元素。",
                "最终值不可能小于全局 gcd，因此目标值就是 g=gcd(a_1,...,a_n)。",
                "若已有元素等于 g，其它每个非 g 元素各用一次操作即可。",
                "若没有 g，需要先找最少多少个数通过连续 gcd 能造出 g，再额外把其余元素改成 g。",
            ],
            "solution_brief": "关键观察：目标一定是全局 gcd。若已有 g，答案就是非 g 元素个数。否则把所有数除以 g，问题变成先造出 1；用 DP 维护造出某个 gcd 值的最少合并次数，转移为 x 与每个 a_i 取 gcd。设造出 1 需要 t 次，那么先花 t 次得到一个 g，再用 n-1 次把其它元素改成 g。",
            "primary_topic": "数论与同余",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2084G1": {
            "statement_brief": "给一个长度为 n 的部分排列，需要把缺失位置补成完整排列。对每个非空子数组玩一个相邻合并游戏，要求最大化所有子数组最终值之和。",
            "transformed_statement": "把题目先看成：子数组游戏本身可以被端点公式消掉，剩下是在数轴上给已知/未知数染两种颜色，使异色点对距离和最小。",
            "key_observations": [
                "归纳可得子数组长度为偶数时结果取两端较小值，长度为奇数时取两端较大值。",
                "所有子数组贡献可化成常数减去一项：奇偶位置不同的数值对之间的距离和。",
                "已出现的数按其所在下标奇偶确定颜色，未出现的数可以选择颜色，但两种颜色数量固定。",
                "按数值从小到大扫，跨过相邻数值时，只需统计左侧黑白数量和右侧黑白剩余数量产生的异色对贡献。",
            ],
            "solution_brief": "关键观察：先证明游戏结果只看子数组两端和长度奇偶，不要在子数组上做博弈。这样最大化总和等价于最小化不同颜色点对的距离和。容易版直接做二维 DP：处理到数值 i，已选 j 个黑点时，先加入切在 i 与 i+1 之间的异色对数量贡献，再决定第 i+1 个数染黑或染白，最后用常数项减去最小代价。",
            "primary_topic": "动态规划与状态设计",
        },
        "2057D": {
            "statement_brief": "数组支持单点修改；每次要在所有子段中最大化 `最大值 - 最小值 - 子段长度差`，输出当前最大便利值。",
            "transformed_statement": "把题目先看成：最优子段的最大值和最小值一定在子段两端，因此目标可以拆成左右端点各自独立的一维表达式。",
            "key_observations": [
                "如果某个最值不在子段边界，就可以从对应边收缩子段，最值不变但长度变短，答案只会更优。",
                "当左端是最小值、右端是最大值时，贡献为 `(a_r-r)-(a_l-l)`。",
                "反向情况同理，需要再维护一套 `(a_i+i)` 相关信息。",
                "合并两个区间时，跨左右儿子的最佳答案只依赖右侧最大值和左侧最小值。",
            ],
            "solution_brief": "关键观察：先把最优段收缩到“两个端点就是最大/最小”。于是正向情况只需维护区间内 `a_i-i` 的最小、最大和最佳差值；线段树合并时取左答案、右答案、右最大减左最小三者最大。再对反向情况维护 `a_i+i` 的同类信息，单点修改后两棵信息一起更新，答案取二者最大。",
            "primary_topic": "数据结构",
        },
        "2022C": {
            "statement_brief": "给 2×n 网格中每个格子的投票对象，要把所有格子划成若干连通三格选区，最大化 Álvaro 赢下的选区数量。",
            "transformed_statement": "把题目先看成：只需要沿列推进铺三连块；状态记录当前列附近是否有一个格子已经被前面的 L 形块占用。",
            "key_observations": [
                "三格选区只有横向三连块和四种 L 形块。",
                "如果某一行放横向三连块，另一行也必须配一个横向三连块，否则会留下无法覆盖的洞。",
                "状态 0 表示当前列之前完整覆盖，状态 1/2 表示下一列上/下行已有一个额外格被占。",
                "每种转移只看接下来两到三列格子的投票数，贡献是对应选区中 Álvaro 是否至少占两格。",
            ],
            "solution_brief": "关键观察：不要把它当任意连通块划分；在 2 行网格里，所有可能块形很少。用 `dp[i][state]` 表示处理到第 i 列附近时的最大票数，状态只保留是否有一个超前格。状态 0 可以放上下两条横块或两种 L 形块进入状态 1/2；状态 1/2 继续放配套横块或补一个 L 形块回到状态 0。枚举这些固定形状即可。",
            "primary_topic": "动态规划与状态设计",
        },
        "2255C": {
            "statement_brief": "两名玩家只能预先约定策略。第一轮看到黑白图和目标格后交换两个格子的颜色；图像随后可被平移、旋转、反射或反色，第二轮要从变换后的图中输出同一个目标格。",
            "transformed_statement": "把题目先看成：在模 n 坐标中用黑格坐标和定义图像的“中心”，让第一轮通过一次交换把这个中心移动到目标格。",
            "key_observations": [
                "设黑格数为 w、黑格坐标和为 S，因为 `gcd(w,n)=1`，`w^{-1}S` 可以作为图像中心。",
                "平移、旋转、反射都会让这个中心像普通格点一样做同样的仿射变换。",
                "反色后黑格数和坐标和都取相反数，中心不变。",
                "交换黑格 p 和白格 p+delta 会让坐标和增加 delta；若找不到这种 p，黑格集合会对非零平移不变并与 `gcd(w,n)=1` 矛盾。",
            ],
            "solution_brief": "关键观察：通信信息藏在一个变换协变的中心里。第一轮计算当前中心 C 和目标 x，令 `delta=w*x-S`，找到一对相差 delta 的黑白格交换，使新中心变成 x。之后无论图像怎么平移、旋转、反射或反色，中心都会和目标格一起变化。第二轮重新计算 `w^{-1}S` 并输出它即可。",
            "primary_topic": "交互",
        },
        "2231B": {
            "statement_brief": "给数组，至多一次选择一个正整数 k 和一个子序列，把子序列所有元素都加 k，判断能否让数组非降。",
            "transformed_statement": "把题目先看成：所有下降相邻对都强制要求右边元素被加 k，因此 k 至少是最大下降差；如果某个 k 可行，取这个最小 k 也可行。",
            "key_observations": [
                "若 `a_i>a_{i+1}`，不加右边元素就不可能修复这对相邻关系，所以必须有 `k>=a_i-a_{i+1}`。",
                "把可行的 k 降到最大下降差，不会破坏同时加或只加左边的相邻关系。",
                "因此只需固定最小可能 k，再从左到右决定哪些元素必须加。",
                "扫描时若当前元素小于前一个最终值，就只能给当前元素加 k；加完仍不够则无解。",
            ],
            "solution_brief": "关键观察：不要枚举 k。先令 k 为所有相邻下降差的最大值；若数组本来有序则直接可行。随后从左到右贪心维护前一个最终值，当前值若已经不小于它就不加，否则必须加 k。若加 k 后仍小于前一个最终值，就说明任何方案都不行；扫完可行则输出是。",
            "primary_topic": "构造与贪心",
        },
        "2217F": {
            "statement_brief": "有两个可向外扩张的区间。第一段区间由 Alice 选择，第二段在给定范围内均匀随机选择；随后双方轮流扩张区间边界，问 Alice 应选哪个第一段来最大化胜率。",
            "transformed_statement": "把题目先看成：每个区间贡献左右两个 Nim 堆，Alice 实际是在选择第一段的异或值，使随机第二段撞上同一异或值的次数最少。",
            "key_observations": [
                "区间 `[l,r]` 可向左扩张 `l-1` 次、向右扩张 `x-r` 次，等价于两个独立石子堆。",
                "总局面是四堆 Nim；Alice 输当且仅当第一段异或值 X 等于随机第二段异或值 Z。",
                "Alice 可以构造任意 `0<=X<x_1`，例如取 `l_1=1,r_1=x_1-X`。",
                "对第二段设 `a=l_2-1,b=x_2-r_2`，约束是 `a,b>=0` 且 `a+b<=x_2-1`；用 `a+b=(a xor b)+2(a&b)` 可把计数变成数位约束。",
            ],
            "solution_brief": "关键观察：胜率最大等价于让随机区间的异或值最少等于自己。枚举 Alice 选择的 X，第二段坏情况满足 `a xor b=X` 且 `a+b<=x_2-1`。令 `K=(a+b-X)/2=a&b`，必须有 `0<=K<=floor((x_2-1-X)/2)` 且 `K&X=0`；每个合法 K 对应 `2^{popcount(X)}` 对 `(a,b)`。数位计数坏情况数量，取最小的 X，再输出 `[1,x_1-X]`。",
            "primary_topic": "博弈",
        },
        "2192D": {
            "statement_brief": "对以 1 为根的树，每个询问根 r 要看 r 的子树。允许在该子树内把一个非根节点的父边断开并接到仍与 r 连通的某点，求子树代价最大值。",
            "transformed_statement": "把题目先看成：一次改边只会让某个被搬子树的所有节点深度同时增加同一个值，收益就是该子树权值和乘以能拉远的深度。",
            "key_observations": [
                "无操作时，父节点子树代价等于所有儿子 `cost(child)+sum(child)` 的和。",
                "若选择搬动 u 的子树，u 子树内每个点深度都增加 x，总代价增量为 `sum(u)*x`。",
                "为了最大化 x，重接点应选在删边后仍属于父侧连通块、且深度最深的位置。",
                "对根 r 的答案，要么操作已在某个儿子子树内部完成，要么直接搬某个儿子子树接到另一个最深位置。",
            ],
            "solution_brief": "关键观察：把改边影响压成“整棵子树统一加深”。一次 DFS 同时算每个节点的子树权值和、无操作代价、子树内最大深度，以及已经用过操作的最佳代价。合并父节点时，基础代价加上各儿子的 `cost+sum`；操作答案取儿子内部最佳，或把某个儿子整棵搬到当前可达最深点，收益为该儿子 `sum` 乘额外深度。",
            "primary_topic": "树结构",
        },
        "2180D": {
            "statement_brief": "给 x 轴上递增的 n 个圆心，要为每个圆心选正半径且圆盘不重叠，最大化相邻相切对数量。",
            "transformed_statement": "把题目先看成：一段连续相切圆的所有半径都由第一个半径 x 唯一决定；每加入一个圆都会给 x 一个开区间限制。",
            "key_observations": [
                "若第一个半径是 x，第二个必须是 `d_1-x`，第三个是 `d_2-d_1+x`，之后半径按距离差交替加减。",
                "每个半径必须大于 0 且小于相邻圆心距离，因此都会转成 x 的一个合法区间。",
                "从左到右维护这些区间交集，第一次交集为空的位置就是当前起点能连出的最长相切前缀。",
                "设 f_i 为从 i 出发的最远可连位置，f_i 单调；每次跳到 `f_i+1` 的贪心是最优的。",
            ],
            "solution_brief": "关键观察：不要猜半径，而是把整段半径都写成第一个半径 x 的线性式。从当前起点开始扫描相邻距离，维护 x 的合法区间交集；交集一空，说明上一位置就是这段最多能连续相切到的地方，答案少一条断边并从这里重新开始。单调性保证每段取最长前缀的贪心不会影响后面最优性，整体线性完成。",
            "primary_topic": "构造与贪心",
        },
        "2173B": {
            "statement_brief": "初始分数为 0。每轮在红牌和蓝牌中选一张：红牌把分数变成 `k-a_i`，蓝牌把分数变成 `b_i-k`，求最后最大可能分数。",
            "transformed_statement": "把题目先看成：为了下一轮蓝牌更优，当前分数反而要尽量小，所以只维护最大值是不够的，必须同时维护可达最小值。",
            "key_observations": [
                "朴素贪心每轮取当前更大的分数会失败，因为蓝牌表达式会把当前分数取相反方向。",
                "下一轮最大值可能来自上一轮最大值走红牌，也可能来自上一轮最小值走蓝牌。",
                "同理，下一轮最小值来自上一轮最小值走红牌，或上一轮最大值走蓝牌。",
                "因此每轮只保留可达分数区间的两端就足够转移。",
            ],
            "solution_brief": "关键观察：蓝牌 `b_i-k` 会把“当前越小越好”引入转移。设上一轮可达最大、最小为 `mx,mn`，则新最大为 `max(mx-a_i, b_i-mn)`，新最小为 `min(mn-a_i, b_i-mx)`。从 `mx=mn=0` 扫一遍，最后输出 `mx`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2124F2": {
            "statement_brief": "从空数组开始，反复追加一个 `1..s` 的循环位移，要求最终长度为 n 且满足若干位置取值限制，统计不同最终数组数量。",
            "transformed_statement": "把题目先看成：同一个数组可能有多种分解方式，必须先规定一种规范分解，再用后缀 DP 统计合法追加。",
            "key_observations": [
                "直接按追加块长度做 DP 会重复计数，例如 `[1,2,1]` 可由两种分解得到。",
                "重复来源是较大恒等排列接在较小恒等排列后，也可换成较小排列加较大循环位移。",
                "题解选择禁止后一种分解，从而给每个数组固定一个规范计数路径。",
                "预处理 `chain(i,j)` 表示从位置 i 开始能连续放 `j,j+1,...` 多久，后续转移就能用后缀和批量完成。",
            ],
            "solution_brief": "关键观察：难点不是普通 DP，而是去掉同一数组的多重分解。先规定禁止“刚放长度 y 的恒等排列后，又放从 y+1 开始的更大循环位移”这类重复路径。然后令 `dp(i,j)` 表示从 i 开始且当前位置放 j 的合法后缀数，`dp2(i)` 汇总所有起始值，`suff(i,j)` 表示准备放 j 时的后缀和。用 `chain(i,j)` 快速判断限制是否允许连续放置，转移即可降到平方复杂度。",
            "primary_topic": "组合计数与概率",
        },
        "2089D": {
            "statement_brief": "给一个长度为 `2n+1` 的二进制串，要在字符间插入 n 个条件运算符并可加括号，判断能否让整个表达式的值为 1，并构造表达式。",
            "transformed_statement": "把题目先看成：每次加括号实际是在把相邻三个字符按三元条件表达式折叠成一个字符；问题变成判断能否通过这些折叠把串变成 1。",
            "key_observations": [
                "若串以 `11` 开头，后面任意折成一位后，最后都能让开头结构产生 1。",
                "若串以 1 结尾，除了最小坏例 `101` 外，也能让最后一次形如 `0?任意:1` 得到 1。",
                "真正困难的是以 0 结尾时，必须制造一对相邻的 1 来改变结尾结构。",
                "可行判据归结为：存在一对相邻的 1，中间 0 的个数为偶数，且前一个 1 之前的字符数为偶数；或串以 1 结尾且不是 `101`。",
            ],
            "solution_brief": "关键观察：把三元表达式当作“三个字符折成一个字符”的局部操作。先处理结尾为 1 的情况，除 `101` 外都可构造。结尾为 0 时，需要通过消掉成对的 0 让某两段 1 变相邻；这要求两次 1 之间有偶数个 0，且前面长度奇偶不会落入坏形 `01100`。扫描相邻 1 对检查这个奇偶条件，满足则按题解的局部构造输出，否则无解。",
            "primary_topic": "构造与贪心",
        },
        "2089A": {
            "statement_brief": "构造一个 1 到 n 的排列，使每个前缀平均值向上取整得到的序列中，至少有约三分之一项是质数。",
            "transformed_statement": "把题目先看成：只要让很多奇数长度前缀的平均值都落在同一个质数 p，就能一次性满足质数数量要求。",
            "key_observations": [
                "伯特兰公设保证在合适区间内能找到一个接近 n/2 的质数 p。",
                "把排列开头构造成 `p,p-1,p+1,p-2,p+2,...`，奇数长度前缀的和正好围绕 p 对称。",
                "这些奇数前缀的平均数向上取整都等于 p。",
                "只要围绕 p 交替放足够多项，质数前缀数量就达到题目要求，剩余数字任意补在后面。",
            ],
            "solution_brief": "关键观察：目标不是让很多不同前缀平均值都是质数，而是让它们都等于同一个质数。先在 n/2 附近找质数 p；然后按 `p,p-1,p+1,p-2,p+2,...` 的顺序放数。每个奇数长度前缀都成对围绕 p 抵消，平均值向上取整为 p，因此前面足够多的奇数前缀贡献质数项。最后把未用数字接上即可。",
            "primary_topic": "构造与贪心",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2071F": {
            "statement_brief": "给数组 a，最多删除 k 个元素。要求剩余序列存在一个中心位置 i，使每个元素都至少达到 p 减去到中心的距离，求最大 p。",
            "transformed_statement": "把题目先看成：固定 p 后，分别求每个位置左侧能形成多长的上升坡、右侧能形成多长的下降坡，两边能接起来就可行。",
            "key_observations": [
                "答案 p 可以二分；难点是固定 p 时快速求最长塔形子序列。",
                "从左到右维护左半坡时，当前最优下标集合只会增加，不需要删除旧元素。",
                "把每个值改成 `p-a_i` 后，一个位置能加入坡，等价于当前前缀中存在非正需求。",
                "加入一个位置后，前面所有未满足需求整体减一，表示它们离中心又远了一格。右侧对称处理。",
            ],
            "solution_brief": "关键观察：固定 p 后，不必枚举中心和删除方案。先从左到右用线段树维护 `p-a_i`，每次找当前前缀最靠右的非正位置，把它加入左坡，然后把它左侧需求整体减一并把该点标成不可再用，得到每个前缀的最长左坡；右侧反向同理。若某个中心左右可保留长度之和达到 n-k，就说明 p 可行，最后二分最大 p。",
            "primary_topic": "数据结构",
        },
        "2071C": {
            "statement_brief": "给一棵树、老鼠起点和陷阱点。要输出一个点的排列作为奶酪出现顺序，使老鼠每步朝当前奶酪走一条边，n 步后必到陷阱点。",
            "transformed_statement": "把题目先看成：以陷阱为根，只要按深度从大到小放奶酪，就能逐层限制老鼠离陷阱的距离。",
            "key_observations": [
                "奶酪在某个点时，老鼠最多沿到该点路径走一步。",
                "如果先处理所有最大深度的点，老鼠最终不可能停在比该深度更深的位置。",
                "继续按深度递减处理，老鼠的深度上界会一层层下降。",
                "最后处理根，也就是陷阱点，老鼠必然被压到陷阱。",
            ],
            "solution_brief": "关键观察：不要试图模拟所有起点路径，直接用深度上界控制。把树以终点为根分层，输出顺序为深度从大到小的所有点。处理完深度 d 的所有点后，老鼠深度不会超过 d；归纳到深度 0 时，最后必在终点。实现就是一次 DFS/BFS 分层再逆深度输出。",
            "primary_topic": "树结构",
        },
        "2071B": {
            "statement_brief": "构造 1 到 n 的排列，使任意前缀和都不是完全平方；若总和本身是完全平方则输出无解。",
            "transformed_statement": "把题目先看成：从自然排列出发，只在三角数前缀变成完全平方的位置与下一项交换。",
            "key_observations": [
                "最终全排列总和固定为 `n(n+1)/2`，如果它是完全平方，则最后一个前缀必坏。",
                "自然排列的第 i 个前缀和就是三角数，只需修掉为平方的那些位置。",
                "若第 k 个前缀和为平方，交换第 k 和第 k+1 项，会把这个前缀和增加 1，立刻避开平方。",
                "题解用夹逼证明相邻两个三角数不可能同时是完全平方，因此这种局部交换不会卡住。",
            ],
            "solution_brief": "关键观察：总和是平方时必无解；否则自然排列几乎可用。扫描 i=1..n，维护三角数是否为平方；一旦第 i 个前缀和是平方，就交换当前位置和下一位置。交换后当前前缀和变成平方数加 1，不是平方；而相邻三角数不会同时为平方，所以下一步仍能继续。",
            "primary_topic": "构造与贪心",
        },
        "2061F2": {
            "statement_brief": "给二进制串 s 和含问号的目标串 t。一次操作可交换 s 中相邻的两个同字符块，求使 s 匹配 t 的最少操作数，无法则输出 -1。",
            "transformed_statement": "把题目先看成：选择哪些原始块保持不动；两个不动块之间的 0 块和 1 块会分别向两侧归并，代价只和中间块数有关。",
            "key_observations": [
                "保持不动的块必须在字符上 0/1 交替，否则中间块无法通过相邻块交换整理。",
                "两个不动块之间，0 会朝相邻 0 不动块一侧移动，1 会朝相邻 1 不动块一侧移动。",
                "容易版目标全确定时，可以贪心验证下一块能否作为不动块。",
                "困难版有问号，需要 DP 选择不动块；每个候选块有可连接的左界和右界，用线段树维护最小转移值。",
            ],
            "solution_brief": "关键观察：操作对象是块，不是单个字符。先把 s 压成块序列，并为每个块判断它能否在 t 中作为一个“不动锚点”。令 `dp(i)` 为第 i 个块保持不动的最小代价，转移枚举前一个不动块 j，合法时加上 `(i-j-1)/2`。困难版把合法 j 的范围整理成左界 `l_i` 和右界 `r_j`，用线段树维护 `2dp(j)-j`，从而把枚举前驱降到对区间取最小。",
            "primary_topic": "数据结构",
        },
        "2057C": {
            "statement_brief": "在区间 `[l,r]` 中选三个不同整数 a,b,c，最大化三对按位异或值之和。",
            "transformed_statement": "把题目先看成：每一位若三个数不全相同，就贡献两次该位权；最高不同位决定理论上界。",
            "key_observations": [
                "某一二进制位在三个数里出现 1 个或 2 个一，三对异或总和都会贡献 `2^{i+1}`。",
                "高于 l 和 r 的最高不同位的所有位都被固定，无法产生贡献。",
                "令 k 为 l、r 的最高不同位，答案上界是低 k+1 位全部产生贡献。",
                "区间内存在唯一一个低 k 位全为 0 的数 x，取 `x` 与 `x-1` 会让低 k 位全部相反，再随便取第三个不同数即可达到上界。",
            ],
            "solution_brief": "关键观察：最大值按位独立看。找到 l 和 r 最高的不同位 k，高位没有贡献，低位最多每位贡献两次。取区间里唯一的 `2^k` 倍数 x，再取 `x-1`，这两个数在低 k 位完全互补；第三个数只要在区间内且不同即可。这样每个低位都不是三数全相同，达到上界。",
            "primary_topic": "构造与贪心",
        },
        "2035D": {
            "statement_brief": "对数组每个前缀，允许把较早偶数中的因子 2 转移到较晚元素上，求经过任意操作后前缀最大和。",
            "transformed_statement": "把题目先看成：因子 2 应尽量从较小的早期数转移到后面更大的奇数底数上；每个新前缀只需要回看最近约 31 个含因子 2 的数。",
            "key_observations": [
                "处理整个数组时，从右往左看，一个数的所有因子 2 都应交给右侧更大的底数；若它已经最大则保留。",
                "前缀在线增长时，新来的数只可能影响它左边少量仍带因子 2 的候选。",
                "因为数值不超过 `10^9`，连续转移约 31 个因子 2 后，接收者一定超过所有原始底数。",
                "因此维护最近 31 个仍可能被重新分配的偶数，其余因子 2 可统一累到当前最大接收者上。",
            ],
            "solution_brief": "关键观察：无限次操作的本质是重新分配因子 2。每个数先拆成奇数底数和 2 的次数，前缀答案维护底数和以及因子 2 的最优归属。加入新数时，只需要把栈里最近不超过 31 个带 2 因子的候选拿出来，尝试是否把它们的 2 转给更靠后的更大底数；超过这个数量后大小差距已经保证统一转移最优。",
            "primary_topic": "数据结构",
        },
        "2246E": {
            "statement_brief": "交互题。隐藏一个位 b、一个 30 位整数 v，以及隐藏运算为按位与或按位或。先查询一次运算结果，再给两个掩码并根据返回值判断 b。",
            "transformed_statement": "把题目先看成：确定性策略会被对手构造两个一致世界骗过，因此需要用随机掩码处理 `v=0` 的退化情况。",
            "key_observations": [
                "若两个最终掩码预先固定，对手可构造一个 v 是查询值的子掩码、另一个 v 是超掩码，使两种 b 的返回完全相同。",
                "当 `v` 非零时，先查询 `x=1` 可以分辨出足够的信息：要么知道运算是或，要么可安全按与处理并知道最低位情况。",
                "已知 v 的某一位后，令两个掩码只在这一位不同，最终返回值即可区分 b。",
                "当 `v=0` 时返回值直接等于某个掩码；给无关高位随机化，可让非零 v 伪装成另一个掩码的概率极小。",
            ],
            "solution_brief": "关键观察：这题不能有可靠确定性解。先查询 `x=1`：若返回值含其它位，说明运算是或并已知道某个 v 的 1 位；否则按与的情况处理。针对非零 v，选择两个只在已知位不同的掩码，最终异或返回能判断 b。针对 `v=0`，随机填充其它位，如果返回值刚好等于某个掩码，就认为是零值情形；误判概率被压到极低。",
            "primary_topic": "交互",
        },
        "2232E": {
            "statement_brief": "n×n 网格要放 n 条只能向右或向下走的蛇，第 i 条长度为 `2i-1`；已有若干蛇固定，求完整摆放方案数。",
            "transformed_statement": "把题目先看成：合法蛇阵与一个 `1..n` 的排列一一对应；固定蛇只是在这个排列上给出相对顺序和位置约束。",
            "key_observations": [
                "观察反对角线：第一个反对角线只会出现最长蛇，后续每条反对角线逐步引入下一条更短的蛇。",
                "相邻两条反对角线能确定一条新蛇相对所有更长蛇是在左侧还是右侧。",
                "因此整张蛇阵可以压成一个排列；每条已放蛇给出若干排列位置约束。",
                "检查固定蛇本身是否对称、是否落在正确反对角线后，剩余自由位置按区间空位数和阶乘计数。",
            ],
            "solution_brief": "关键观察：不要在二维网格里直接计数。沿左下到右上的反对角线看，每前进一步只是在已有长蛇排列中插入一条新短蛇，所以完整摆放等价于排列。对每条预放蛇，先验证起点、路径和中心对称条件，再把它转成对若干插入位置的约束。按蛇长从大到小处理这些约束，遇到必须从增到减的唯一转折，乘上可选空位数；未受约束的短蛇最后用阶乘排列。",
            "primary_topic": "组合计数与概率",
        },
        "2232D": {
            "statement_brief": "有 n 层从小到大的蛋糕和 3 个位置。第 i 层只有当它上方恰有 `a_i` 层时才能移动；要在 `2^n` 步内把整塔搬到目标位置，或判断无解。",
            "transformed_statement": "把题目先看成：这是带额外可移动条件的汉诺塔递归；只要每层要求的上方层数小于它的编号，就能递归搬运。",
            "key_observations": [
                "若 `a_i>=i`，第 i 小层最多只有 i-1 层能放在它上方，因此永远不可移动。",
                "若所有 `a_i<i`，可用类似汉诺塔的强归纳构造。",
                "当最大层要求 0 层在上方时，先搬走上面所有层，再搬它，再把上面层搬回目标。",
                "当最大层要求至少 1 层在上方时，只先搬走不需要压在它上方的那部分，搬它后再把这部分搬回，最后整体搬目标。",
            ],
            "solution_brief": "关键观察：可行性就是每层 `a_i<i`。构造函数 `moveall(k,s,t)` 搬前 k 层：若第 k 层要求上方 0 层，就按普通汉诺塔先搬 k-1 层到辅助柱、搬第 k 层、再搬回；若要求 `a_k>0`，先只搬走 `k-1-a_k` 层，让第 k 层上方正好剩 a_k 层，搬第 k 层后再复原这些小层，最后递归搬前 k-1 层。归纳可证步数不超过 `2^k-1`。",
            "primary_topic": "构造与贪心",
        },
        "2220B": {
            "statement_brief": "一排守卫的计时器模 m 增长，计时器为 0 时会抓当前位置的人。主角每秒可停留或左右移动，问能否从左侧安全走到右侧。",
            "transformed_statement": "把题目先看成：相同初始计时值的连续段最危险；只要每段长度小于 m，就能等待它的安全窗口再穿过。",
            "key_observations": [
                "如果有长度至少 m 的相同值连续段，穿过它至少要 m 秒，而这段中每个位置在任意 m 秒内都会出现危险时刻。",
                "因此这种长段必然无法安全通过。",
                "若每个相同值段长度都小于 m，则每段存在一个短于 m 的时间窗口，段内所有守卫都不看守。",
                "相邻段初始值不同，危险时刻错开，可以在段外等待窗口后逐段穿过。",
            ],
            "solution_brief": "关键观察：只看连续相等段。长度 ≥m 的段必死，因为跨段所需时间覆盖完整模周期；反过来，所有段长度 <m 时，站在段外等到这一整段都安全的窗口，然后一口气穿过。相邻段值不同保证窗口可逐段衔接，所以扫描最大相等段长度即可判断。",
            "primary_topic": "构造与贪心",
        },
        "2211F": {
            "statement_brief": "统计所有长度 n、值域 1..m 的非降数组，对每个可能查找值运行给定二分函数后，把返回深度总和累加。",
            "transformed_statement": "把题目先看成：先算二分递归树里每个下标的权重，再把非降数组按数值分成 m 个连续段来计数。",
            "key_observations": [
                "固定一个数值 x 覆盖的下标区间 `[l,r]` 后，左边只能填 1..x-1，右边只能填 x+1..m。",
                "两侧非降填法由隔板法给出，乘积形式可用范德蒙德恒等式合并。",
                "合并后除区间长度外其余基本是常数，于是需要按长度统计所有区间最小二分权重之和。",
                "所有长度的区间最小值贡献可用单调栈确定支配范围，再用二阶差分批量加三角形贡献。",
            ],
            "solution_brief": "关键观察：不要枚举数组。先模拟二分递归得到每个位置被访问时的深度权重。对非降数组，某个值 x 出现的一段 `[l,r]` 一旦确定，左右两边填法是两个隔板计数；用范德蒙德恒等式把对 x 的求和压成只依赖段长的组合数。于是剩下的核心是：对每个长度 k，求所有长度 k 区间的最小权重和。用单调栈算每个位置作为最小值的左右范围，再用差分维护它对不同 k 的贡献。",
            "primary_topic": "组合计数与概率",
        },
        "2201D": {
            "statement_brief": "数组支持单点修改。定义两个等长子段若多重集合相同则形成三元组 `(i,j,k)`；每次询问最大 k 以及达到最大 k 的三元组数量。",
            "transformed_statement": "把题目先看成：最大 k 其实只由相同值的最远两次出现决定；计数再转成维护这些最远距离候选形成的连续链。",
            "key_observations": [
                "若 `a_i=a_j`，则长度 `j-i` 的相邻两段 `[i,i+k-1]` 和 `[i+1,i+k]` 多重集合相同。",
                "反过来若存在更长好三元组，左段独有的 `a_i` 必须在右段独有部分出现，会推出一对相同值距离至少 k，矛盾于最远相等距离。",
                "所以 `k_max` 等于所有相同值下标最大距离的最大值；每个值只贡献最左和最右这一对候选。",
                "固定当前最大 k 后，若相邻起点的一串候选都存在，则这串中的任意两个端点都能组成好三元组，贡献为组合数。",
            ],
            "solution_brief": "关键观察：先证明最大长度就是相同值最远距离。为每个值维护出现位置集合和候选距离，把所有候选距离放入全局集合即可得到 `k_max`。为了算达到最大值的数量，维护每个距离 d 下候选起点形成的连续区间；插入或删除一个候选起点时合并/拆分区间，并维护每个区间长度对 `C(len+1,2)` 的贡献。单点修改只影响旧值和新值的最左/最右候选。",
            "primary_topic": "数据结构",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2194D": {
            "statement_brief": "给一个 0/1 矩阵，要用一条只向右和向下、从左上到右下的折线把矩阵分成两部分，最大化两部分 1 的数量乘积，并输出一种切法。",
            "transformed_statement": "把题目先看成：若矩阵里总共有 k 个 1，最优就是把一侧的 1 数量凑到 `floor(k/2)`；剩下只是构造一条能精确包住这些 1 的单调折线。",
            "key_observations": [
                "乘积 `a*(k-a)` 在 a 最接近 k/2 时最大，所以目标侧 1 的数量固定为 `floor(k/2)`。",
                "按行统计 1 的前缀，先找到最后一个整行前缀不超过目标的位置。",
                "在下一行里从右侧或左侧取刚好缺少的若干个 1，就能把目标侧数量补满。",
                "切线只需先沿行走到该行，再在该行内绕过选定后缀，最后走到终点。",
            ],
            "solution_brief": "关键观察：最大乘积只关心两边 1 的数量是否接近一半。设目标数量为 `floor(k/2)`，逐行累加 1，找到不能再整行加入的位置；下一行只拿刚好需要的若干个 1，并据此恢复一条右/下路径。这样一侧恰有目标个 1，另一侧是剩余个数，乘积达到理论最大。",
            "primary_topic": "构造与贪心",
        },
        "2180B": {
            "statement_brief": "依次给出若干字符串，每次可以把当前字符串接到答案开头或结尾，求最终字典序最小的字符串。",
            "transformed_statement": "把题目先看成：每一步只需要比较“放前面”和“放后面”两个结果；局部字典序最小会导向全局最小。",
            "key_observations": [
                "题解用反证说明：若某一步没有得到当前可达的最小中间串，后续只是在两侧继续拼接，无法补回这个首个差异。",
                "因此处理第 i 个字符串时，只比较 `当前+新串` 与 `新串+当前`。",
                "取字典序较小的一个作为新当前串即可。",
                "总长度只有 4000，直接字符串比较和拼接足够。",
            ],
            "solution_brief": "关键观察：不要回溯每个字符串放哪边。维护当前最小串 s，读到新串 t 时，只有 `s+t` 和 `t+s` 两种可能；如果较差方案在这一刻已经字典序更大，后续再往两边拼相同的剩余字符串也不能让它反超。于是每步取二者较小值。",
            "primary_topic": "字符串",
        },
        "2164H": {
            "statement_brief": "给一个字符串和大量区间询问。每次询问子串中最长的、至少出现两次的回文串长度。",
            "transformed_statement": "把题目先看成：两次出现的回文要么相交，要么不相交；相交情况可化为某个大回文的最长回文 border，不相交情况只需保留少量代表对。",
            "key_observations": [
                "若两个回文出现区间相交，它们会同时成为覆盖大区间的 border，且覆盖大区间本身也是回文。",
                "对任意区间，只需考虑最长回文前缀、最长回文后缀以及它们中心之间的回文结构。",
                "不相交回文对很多，但真正可能更新答案的对只有 `O(n log n)` 个。",
                "前缀的回文后缀可分成若干长度成等差数列的系列，同一系列内部的相交贡献已由第一部分处理，只需看系列首尾代表。",
            ],
            "solution_brief": "关键观察：先把重复回文分成相交和不相交两类。相交时，答案来自某个回文串的最长回文 border，可用回文自动机和马拉车预处理区间信息。不相交时，扫描右端点，把当前前缀的回文后缀按等差长度系列压缩；同一系列中大部分对只会重走相交情况，所以只保留首尾代表加入离线结构。最后用这些候选回答区间询问。",
            "primary_topic": "字符串",
        },
        "2133A": {
            "statement_brief": "给若干齿轮齿数，问能否重新排成一排，使最右齿轮转速仍为每秒 1 圈。",
            "transformed_statement": "把题目先看成：相邻齿轮转速比例会连乘抵消，最终只取决于最左和最右两个齿轮的齿数。",
            "key_observations": [
                "若排列后齿数为 `b_1..b_n`，最右转速等于 `1*b_1/b_n`。",
                "中间所有相邻比例 `b_i/b_{i+1}` 都会相互抵消。",
                "要让最右转速等于 1，必须且只需 `b_1=b_n`。",
                "因此存在两个齿数相同的齿轮即可，把它们放在两端。",
            ],
            "solution_brief": "关键观察：传动链不是复杂模拟，而是望远镜乘积。最终转速只剩最左齿数除以最右齿数，所以问题等价于数组里是否有重复值。有重复输出可行，否则不可行。",
            "primary_topic": "基础实现与模拟",
        },
        "2109C3": {
            "statement_brief": "交互题。隐藏数 x 在 1 到 1e9 之间，要用尽量少的命令把它变成给定 n；困难版要求证明最少命令数。",
            "transformed_statement": "把题目先看成：需要一个乘数把所有可能 x 的数位和变成同一个常数，然后再一次加法调到 n。",
            "key_observations": [
                "核心恒等式是：对 `1<=x<=10^d`，`x*(10^d-1)` 的数位和恒为 `9d`。",
                "取 `d=9`，先乘 `999999999`，再执行一次数位和命令，任何隐藏 x 都会变成 81。",
                "若目标 n 不是 81，再加 `n-81` 即可；若 n 是 81，只需前两步。",
                "题解还证明两步只可能在 n=81 时成功，其它目标无法把所有初始 x 同时压成指定值。",
            ],
            "solution_brief": "关键观察：用 `10^9-1` 制造九位补数。因为 `x*(10^9-1)=(x-1)*10^9+(10^9-1-(x-1))`，两部分对应位相加都为 9，所以数位和固定为 81。命令序列就是乘 `999999999`、取数位和、必要时加到 n；n=81 时省掉最后一步。",
            "primary_topic": "数论与同余",
        },
        "2107B": {
            "statement_brief": "若干盒苹果，两人轮流取一个。每次取完后若最大值和最小值差超过 k，刚取的人输；否则无苹果可取的人输，判断赢家。",
            "transformed_statement": "把题目先看成：只要当前最大最小差不超过 k，总能安全地从最大盒取一个；因此多数情况只看总苹果数奇偶。",
            "key_observations": [
                "在合法局面中，从最大元素减一不会增大最大最小差；全相等时减一后差为 1，也合法。",
                "所以一旦首步能进入合法局面，后续双方都能一直安全取到苹果用完。",
                "唯一额外检查是 Tom 第一手从最大盒取一个后，数组是否已经满足差值限制。",
                "若首步可行，游戏长度固定为苹果总数，奇数 Tom 赢，偶数 Jerry 赢。",
            ],
            "solution_brief": "关键观察：合法状态不会被迫走死，只要一直取当前最大盒即可保持合法。先模拟 Tom 必须做的最优首步：把一个最大值减一，再看最大最小差是否仍大于 k；若大于则 Tom 立即输。否则后续只是每回合总和减一，按总和奇偶判断最后行动者。",
            "primary_topic": "博弈",
        },
        "2101B": {
            "statement_brief": "给一个排列，操作可把连续四个位置 `[a_i,a_{i+1},a_{i+2},a_{i+3}]` 变成 `[a_{i+2},a_{i+3},a_i,a_{i+1}]`，求可达的字典序最小排列。",
            "transformed_statement": "把题目先看成：操作不会改变元素所在位置的奇偶性，也不会改变某个全局逆序奇偶约束；先分别排序奇偶位，再修正最后的奇偶性。",
            "key_observations": [
                "每个元素每次只移动 2 格，所以所在下标奇偶不变。",
                "除最后少数位置外，奇数位内部和偶数位内部可以充分重排。",
                "操作本身是偶排列，因此整体逆序数奇偶保持不变。",
                "把奇偶位分别排序后，若逆序奇偶不匹配，只能在最后同奇偶的两个位置交换一次来恢复可达性。",
            ],
            "solution_brief": "关键观察：可达集合由两个不变量控制：位置奇偶和逆序数奇偶。先取出原排列奇数位元素、偶数位元素分别排序，并按原奇偶位置放回，这给出忽略逆序奇偶时的字典序最小候选。再比较原始奇偶位内部逆序奇偶是否匹配；若不匹配，交换末尾两个同奇偶位置的元素，这是对字典序影响最小的修正。",
            "primary_topic": "构造与贪心",
        },
        "2257C": {
            "statement_brief": "根树中海狸从根走到若干候选水坝之一。可以在边上放摄像头，若经过会被记录；求最少摄像头及放置边，使能唯一确定终点。",
            "transformed_statement": "把题目先看成：摄像头边被删后，所有候选水坝必须落在不同连通块；树上分开 m 个目标点至少需要 m-1 条边。",
            "key_observations": [
                "若删去摄像头边后某个连通块内仍有两个水坝，它们经过的摄像头集合相同，无法区分。",
                "树上要把 m 个指定点全部分开，至少删 m-1 条边。",
                "如果根本身是水坝，就给其它每个水坝通向父亲的边放摄像头。",
                "如果根不是水坝，可以少跳过一个最靠近根的水坝父边，因为其余水坝被切开后它所在块不会含第二个水坝。",
            ],
            "solution_brief": "关键观察：摄像头记录等价于删边后的连通块编号。答案下界是 m-1；构造时对每个水坝通常选它连向父亲的边。若根是水坝，除根外全选；若根不是水坝，就跳过一个深度最小的水坝，其它水坝父边全选。这样每个候选终点都落入不同块，且摄像头数达到下界。",
            "primary_topic": "树结构",
        },
        "2246A": {
            "statement_brief": "构造一个偶数长度排列，使无论每个位置选择加上、减去或忽略 `i*p_i`，最终计数器都不可能等于 1。",
            "transformed_statement": "把题目先看成：只要所有 `i*p_i` 都是偶数，那么任意加减和仍是偶数，自然不可能得到 1。",
            "key_observations": [
                "最终值由若干个 `i*p_i` 带符号相加组成。",
                "如果每一项都是偶数，最终值一定是偶数。",
                "偶数 n 下，把奇数位置放偶数、偶数位置放奇数即可。",
                "直接输出反序排列时，位置 i 与值 `n-i+1` 奇偶相反，所以乘积总为偶数。",
            ],
            "solution_brief": "关键观察：不需要研究所有子集和，只需把奇偶性封死。因为 n 为偶数，反序排列 `n,n-1,...,1` 让每个位置 i 和对应值奇偶相反，于是 `i*p_i` 全是偶数；任意加、减或不选后总和仍为偶数，绝不可能是 1。",
            "primary_topic": "构造与贪心",
        },
        "2237G": {
            "statement_brief": "双轮通信题。第一轮要把原数组编码成较短数组 b；第二轮只能询问 b 中两数的最大公因数，需恢复原数组。",
            "transformed_statement": "把题目先看成：用若干质数幂作为基底，之后每个编码数都选只含这些小质数的平滑数；查询最大公因数即可恢复它的质因数分解。",
            "key_observations": [
                "若 b 中预先放入 `p^k<=10^6` 的最大质数幂，询问它与 x 的最大公因数，就能知道 x 中 p 的幂次贡献。",
                "取前 110 个质数作为基底，足够产生很多不超过 `10^6` 的平滑数。",
                "把每个原数写成 20 位二进制，串起来后按 18 位分块，每块映射到一个平滑数。",
                "第二轮对每个编码块询问所有基底，乘回各质数贡献即可得到平滑数，再反查出 18 位块。",
            ],
            "solution_brief": "关键观察：最大公因数查询天然适合读质因数指数。第一轮先放 110 个质数幂基底，再把原数组的二进制串按 18 位切块，用预处理的平滑数表编码每块。第二轮知道前 110 个位置是基底，对每个后续编码数分别与这些基底询问最大公因数，乘起来恢复该平滑数，查表得到 18 位信息，最后按 20 位切回原数组。",
            "primary_topic": "交互",
        },
        "2211G": {
            "statement_brief": "给整数数组，可反复把相邻两项都替换成它们的平均值，问能否最终变成非降序列。",
            "transformed_statement": "把题目先看成：看前缀和折线。数组非降等价于前缀和点列下凸；一次操作就是把某个局部三点中间拉到两端连线上。",
            "key_observations": [
                "令 `b_i` 为前缀和，则 `a_i` 非降等价于点 `(i,b_i)` 的斜率非降，也就是折线下凸。",
                "对任意一段，连续平均操作可以让这一段任意接近两端连线。",
                "如果存在点严格低于首尾连线，可以先把左右两段拉平，再从该点向两侧扩展出一段下凸区间，最终全局可行。",
                "若没有点低于首尾连线，则只能把高于连线的点压到线上；若有两个相邻点都高于连线，就无法一次局部拉直解决。",
            ],
            "solution_brief": "关键观察：把平均操作几何化。前缀和折线要变成下凸；操作会把中间点放到相邻两点连线上，并且可把任意一段无限接近直线。若某点在首尾连线下方，就能以它为核心扩展出全局下凸形状。否则所有点都在连线上方，只能逐个消掉高点；这要求不存在两个相邻高点。按这两个条件线性判断即可。",
            "primary_topic": "几何",
        },
        "2209F": {
            "statement_brief": "树上每点有值。每次选根 r，把 r 的当前值加入总和并清零；其余非叶点的值会沿当前根向下转移到最深且编号最小的叶子。要求经过 k 次操作后总和最大。",
            "transformed_statement": "把题目先看成：第一次操作后所有值都会集中到叶子，之后只是在固定的一批叶子值中贪心取最大的若干个；难点是枚举第一次选哪个根。",
            "key_observations": [
                "第一次重根并转移后，所有非叶值都被推到某些叶子上，此后值分布固定在叶子上。",
                "后面 k-1 次只需要每次取当前最大叶子值。",
                "相邻两个根之间换根时，受影响的值只发生在当前节点和父节点相关的两处转移。",
                "因此可以树形换根维护第一次选根后的叶子值集合，并用有序集合维护后续最大 k-1 个值之和。",
            ],
            "solution_brief": "关键观察：把所有复杂性集中到第一次操作。枚举第一次根 r 时，模拟一次“非叶值流向最远叶子”的结果；之后再选根只是在叶子值中拿最大的 k-1 个。用换根 DFS 从父根移动到子根时，只有沿这条边附近的归宿会变化，维护叶子值多重集合以及前 k-1 大的和，就能对每个 r 求 `a_r + 后续最大和` 并取最大。",
            "primary_topic": "树结构",
        },
    }
)


PROBLEM_OVERRIDES.update(
    {
        "2176E": {
            "statement_brief": "有一列元素，每个元素有值和删除代价。每次只能在相邻两元素中删除值较小者，并支付两者较小删除代价；还会依次把某些元素删除代价清零，要求每次后的最小总删除费用。",
            "transformed_statement": "把题目先看成：最大值会把区间切开；一个区间内的最大值们必须至少有一个被外部元素删除，其余最大值和子区间递归独立处理。",
            "key_observations": [
                "没有询问时，对区间递归看所有最大值位置；最大值之间的子段互不影响。",
                "设外部可用的最小删除代价为 x，本层最大值的有效代价会更新成这些最大值代价和 x 的最小值。",
                "由最大值分割形成的递归调用本身是一棵树，可以记录每个元素最终按哪个代价被删除。",
                "某个元素代价清零时，只会影响递归树中包含它作为本层最大值的那棵子树；已经清零过的部分可跳过。",
            ],
            "solution_brief": "关键观察：删除过程的结构由区间最大值决定。先递归建一棵“最大值分割树”，并记录每个元素当前贡献的删除代价。查询把某个 `c_p` 置零时，找到 p 所属的递归节点，沿其子树把尚未被清零影响的贡献改成 0，同时更新全局答案。建树需要区间最大查询，清零传播用并查集/跳指针避免重复访问，总体近似线性对数。",
            "primary_topic": "数据结构",
        },
        "2165E": {
            "statement_brief": "给树的边染色，必须恰好使用 k 种颜色。一条路径的代价是路径上出现的颜色数，要求对每个 k 求最小可能的最大路径代价。",
            "transformed_statement": "把题目先看成：反过来固定最大路径颜色数 d，求最多能使用多少种连通颜色块；答案由树的中心和向叶子剥层结构决定。",
            "key_observations": [
                "同一种颜色分散成多个连通块没有好处，可以把最外层组件改成相邻颜色而不增大路径颜色数。",
                "因此每个颜色都可视为树上的一个连通边块。",
                "固定允许代价 d 后，最优形状围绕一个类似直径中心的点或中心颜色块展开。",
                "奇数 d 时保留一个中心颜色块，偶数 d 时保留一个中心点；向外剥掉若干层叶子就能统计可用颜色数。",
            ],
            "solution_brief": "关键观察：不要直接对每个 k 染色，而是固定答案 d 求最多颜色数。先证明颜色块可以连通，然后最优方案一定从中心往叶子方向推颜色。用剥叶过程维护剩余树大小和最大度：奇数 d 对应删掉最外 `(d-1)/2` 层叶子，偶数 d 对应删掉最外 `d/2-1` 层后再看剩余树最大度。把每个 d 能支持的颜色数记录下来，最后对 k 做后缀最小。",
            "primary_topic": "树结构",
        },
        "2155D": {
            "statement_brief": "交互题。有 n 节电池，其中至少 a 节可用但 a 未知且判定可自适应变化。每次可测试一对电池，需要在 `floor(n^2/a)` 次内找到一对同时可用的电池。",
            "transformed_statement": "把题目先看成：把电池放在环上，任意 a 个可用点中一定存在一对环距离不超过 `floor(n/a)`。",
            "key_observations": [
                "把可用电池按环上顺序排列，相邻可用电池之间的弧长总和为 n。",
                "由平均值，至少一段相邻可用电池距离不超过 `floor(n/a)`。",
                "因此按距离 1、2、3…… 枚举所有间隔为该距离的电池对，一定会在距离不超过 `floor(n/a)` 时命中可用对。",
                "前 `floor(n/a)` 个距离总共测试不超过 `n*floor(n/a)<=floor(n^2/a)` 对。",
            ],
            "solution_brief": "关键观察：不知道 a 也没关系，策略按环距离从小到大扫。对每个距离 d，测试所有 `(j,j+d)` 环上电池对；若真实可用电池数为 a，则某对相邻可用电池的环距离必不超过 `floor(n/a)`，所以在预算用完前必然找到一对好的。",
            "primary_topic": "交互",
        },
        "2153F": {
            "statement_brief": "给一个满足不存在 `[x,y,x,y]` 交错子序列的数组，在线回答区间内出现奇数次的不同值之和。",
            "transformed_statement": "把题目先看成：`[x,y,x,y]` 不存在意味着值的出现区间像括号一样嵌套，可以把数组建成一棵 DFS 序正好为原数组的树。",
            "key_observations": [
                "扫描数组时，某个值第一次出现入栈，最后一次出现出栈；当前栈顶就是新位置在树上的父亲。",
                "可爱数组性质保证最后一次出现时弹出的确实是同一个值，否则会形成交错模式。",
                "相同值在这棵树中形成一个连通块，因此区间奇偶贡献可按树路径和子树拆分。",
                "询问 `[l,r]` 可按 l、r 在树上的最近公共祖先分成左端尾段、中间若干完整子树、右端前段三部分。",
            ],
            "solution_brief": "关键观察：把数组的交错限制转成树结构。建树后，原数组就是这棵树的 DFS 序，同值点连成块。预处理全局前缀/后缀的奇偶值和、每个子树的奇偶值和，以及每个节点儿子序列的前缀贡献。回答区间时求 l 和 r 的最近公共祖先，左侧残段用后缀差，右侧残段用前缀差，中间完整儿子区间用预处理前缀和，在线解码后仍能对数处理。",
            "primary_topic": "树结构",
        },
        "2116B": {
            "statement_brief": "给两个 0 到 n-1 的排列 p、q。对每个 i，计算 `max_{0<=j<=i}(2^{p_j}+2^{q_{i-j}})` 并取模输出。",
            "transformed_statement": "把题目先看成：比较两个二的幂之和，先比最大指数，再比最小指数；因此每个 i 只需看 p 前缀最大和 q 前缀最大对应的两个候选。",
            "key_observations": [
                "`2^a+2^b` 的大小由 `{a,b}` 排序后的字典序决定。",
                "因为 p、q 都是排列，当前 i 的最优候选一定包含 p 前缀最大值或 q 前缀最大值之一。",
                "若最大指数来自 p 的位置 j，则另一个指数被强制为 `q_{i-j}`；q 对称同理。",
                "每个 i 维护 p、q 的前缀最大位置，比较两种候选即可。",
            ],
            "solution_brief": "关键观察：最大的一项二次幂压倒所有更小指数之和，所以先抢最大指数。遍历 i 时维护 p[0..i] 最大值的位置 jp 和 q[0..i] 最大值的位置 jq；答案只可能是 `2^{p_jp}+2^{q_{i-jp}}` 或 `2^{p_{i-jq}}+2^{q_jq}`。按最大指数、次大指数比较选更大者，再用预处理二次幂取模输出。",
            "primary_topic": "构造与贪心",
        },
        "2115C": {
            "statement_brief": "有若干怪物血量，目标是在 m 轮内把所有血量降到 1。每轮先知道剑是否发光：发光时攻击会全体减一，不发光时可单点减一；可选择是否攻击，求最优成功概率。",
            "transformed_statement": "把题目先看成：先必须用若干次单点攻击把所有怪物削到同一最低血量附近，之后状态只剩最低血量和“有多少怪物比最低值高一”。",
            "key_observations": [
                "若当前最低血量为 l，全体攻击最多只能做 l-1 次。",
                "每个怪物至少需要 `h_i-l` 次单点攻击，因此初始必须完成的单点攻击总数 s 是硬门槛。",
                "前 s 次不发光时一定应该单点攻击；题解枚举第 s 次不发光发生在哪一轮，把过程分成前后两段。",
                "完成拉平后，最优单点攻击总是打当前最高血量怪物，状态压缩为不足 n 的差异计数。",
            ],
            "solution_brief": "关键观察：策略分两阶段。先设最低血量为 l，计算所有怪物超过 l 的总差 s；如果不发光次数少于 s，一定失败，所以前 s 次不发光必须用来补齐差距。用概率 DP 统计第 s 次不发光落在第几轮。之后所有怪物血量几乎相同，单点攻击总打最高者不会变差，只需用压缩状态 DP 处理剩余轮数和最低血量，合并两段概率得到答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2109C2": {
            "statement_brief": "交互题。隐藏数 x 在 1 到 1e9 之间，要用不超过 4 条命令把它变成给定 n。",
            "transformed_statement": "把题目先看成：先乘 9，再连续取两次数位和，可以把任意隐藏 x 压成固定值 9。",
            "key_observations": [
                "乘 9 后，数值的数位和一定是 9 的倍数。",
                "由于原始 x 不超过 1e9，乘 9 后第一次取数位和只会落在 9、18、27、……、81 这些值。",
                "这些值再取一次数位和都会变成 9。",
                "最后加上 `n-9` 就能得到目标 n。",
            ],
            "solution_brief": "关键观察：四步内可以先把所有可能 x 归一化。命令固定为：乘 9，取数位和，再取数位和，此时无论初始 x 是多少都变成 9；最后执行加 `n-9`。这是中等版，不需要证明最少性，只要保证四条命令内成功。",
            "primary_topic": "数论与同余",
        },
        "2097B": {
            "statement_brief": "网格上一条简单路径只保留了奇数位置的格子，需要补出每个偶数位置，统计完整路径方案数。",
            "transformed_statement": "把题目先看成：每个缺失偶数格只可能是一个固定格，或在两个候选格里二选一；再把所有二选一限制变成图上的匹配选择问题。",
            "key_observations": [
                "若相邻两个已知奇数格曼哈顿距离不是 2，答案为 0。",
                "若它们同行或同列，中间偶数格唯一；否则偶数格有两个拐角候选。",
                "把每个缺失位置看成一条边：唯一候选是自环，两个候选是连接两个格子的边。",
                "要求补出的格子互不相同，等价于给每条边选择一个端点，且每个点最多被选一次；每个连通块可独立计数。",
            ],
            "solution_brief": "关键观察：路径简单性的冲突只发生在缺失偶数格之间。为每个缺失位置建一条候选边，问题变成每条边选一个端点且端点不重复。连通块若边数大于点数无解；若边数等于点数，则唯一环块贡献 1 或 2；若是树，选哪个点不被占用后其它选择全确定，贡献为点数。各连通块贡献相乘。",
            "primary_topic": "图论与网络流",
        },
        "2096F": {
            "statement_brief": "有若干关于玩家身份的区间陈述：某区间没有冒充者，或某区间至少有一个冒充者。多次询问一段陈述能否同时为真。",
            "transformed_statement": "把题目先看成：0 类陈述会把若干位置强制成好人；一组陈述矛盾当且仅当某个 1 类区间被这些 0 区间的并完全覆盖。",
            "key_observations": [
                "判断一组陈述可满足时，可以先把所有 0 区间覆盖的位置设为好人，其余位置设为冒充者。",
                "于是只需检查每个 1 区间里是否还有至少一个未被 0 区间覆盖的位置。",
                "可满足性对询问区间有单调性：删掉左端或右端陈述不会让可满足变坏。",
                "用双指针预处理每个右端最小可行左端；维护当前 0 区间覆盖计数和是否存在被覆盖的 1 区间。",
            ],
            "solution_brief": "关键观察：矛盾只有一种形态：某个“至少一个冒充者”的区间被“全是好人”的区间并盖满。对陈述下标用双指针滑窗，右端加入新陈述后，若窗口不可满足就不断移出左端。数据结构上，0 区间用覆盖计数线段树维护最小覆盖；加入 1 区间时查它是否有未覆盖点，加入 0 区间时还要看合并后的 0 连通段是否完全盖住某个已存在 1 区间。预处理 `low[r]` 后，询问 `[l,r]` 只需判断 `l>=low[r]`。",
            "primary_topic": "数据结构",
        },
        "2096B": {
            "statement_brief": "抽屉里有每种颜色的左手套和右手套。求最少抽出多少只，才能保证至少得到 k 种不同颜色的配对。",
            "transformed_statement": "把题目先看成：先构造最多只能形成 k-1 种配对的最坏抽法，答案就是这个最大数量加一。",
            "key_observations": [
                "若完全不想形成配对，每种颜色最多只能取左手套和右手套中较多的一侧。",
                "若允许形成 m 种颜色的配对，就额外选 m 个颜色，把这些颜色较少的一侧也全部取走。",
                "为了让最坏抽法尽量多，应选择较少侧数量最大的 m 个颜色。",
                "令 m=k-1，最多坏抽法数量加一就是保证 k 种配对的最小抽取数。",
            ],
            "solution_brief": "关键观察：从反面算。对每种颜色，先取 `max(l_i,r_i)` 只可以避免产生该颜色配对；若允许最多 k-1 种颜色配对，再挑 k-1 个 `min(l_i,r_i)` 最大的颜色，把另一侧也取完。这个数量 y 是还不能保证 k 对的最大抽取数，答案为 `y+1`。",
            "primary_topic": "构造与贪心",
        },
        "2077E": {
            "statement_brief": "数组表示纸带每格需要染黑的次数。一次操作可任意折纸后滴一次墨，求每个子数组所需最少操作数的总和。",
            "transformed_statement": "把题目先看成：折叠后一次滴墨会选出下标奇偶交替的一组格子；令 `b_i=(-1)^i a_i` 后，最少次数等于 b 的最大绝对子段和。",
            "key_observations": [
                "一次折叠滴墨命中的格子下标奇偶必须交替。",
                "对交替符号数组 b，一次操作使任意子段和的绝对值最多减少 1，因此最大绝对子段和是下界。",
                "题解给出贪心选交替非零位置，可让所有达到最大绝对值的子段同时下降 1，因此下界可达。",
                "最大绝对子段和等于前缀和数组的最大值减最小值。",
            ],
            "solution_brief": "关键观察：先把折纸操作翻译成奇偶交替选择。对 `b_i=(-1)^i a_i`，每次操作最多把任意子段和绝对值降低 1，而贪心选择交替非零位置可以同步降低所有最坏子段，所以 `f` 就是最大绝对子段和。对所有子数组求和时，转为对前缀和数组求所有区间的 `最大值-最小值` 之和，分别用单调栈统计每个前缀作为最大/最小的贡献。",
            "primary_topic": "数据结构",
        },
        "2057E2": {
            "statement_brief": "给带权无向图和询问 `(a,b,k)`，要求从 a 到 b 的路径中，第 k 大边权尽量小，输出这个最小值；困难版边数不再受额外限制。",
            "transformed_statement": "把题目先看成：固定阈值 x 后，把不超过 x 的边当 0、超过 x 的边当 1；只要 0/1 最短路小于 k，说明第 k 大边权可以不超过 x。",
            "key_observations": [
                "对某个 x，路径上超过 x 的边数少于 k，等价于第 k 大边权不超过 x。",
                "按边权从小到大把边权从 1 改成 0，可以维护任意点对之间的 0/1 最短路。",
                "把一条边改成 0 后，所有点对距离只需尝试经过这条新 0 边的两种方向，平方时间即可更新。",
                "困难版中，如果新 0 边连接的两个点已在同一个 0 边连通块内，所有 0/1 最短路不会变化，这一层可以跳过；真正变化最多 n-1 次。",
            ],
            "solution_brief": "关键观察：把“第 k 大边最小化”变成阈值判定。预处理若干层全点对 0/1 最短路：按权值加 0 边，只有当这条边合并两个 0 连通块时才生成新层，并用 `d'[i][j]=min(d[i][j],d[i][u]+d[v][j],d[i][v]+d[u][j])` 更新。层数最多 n-1，所以预处理为立方级；每个询问在这些层上二分，找最早使 `dist[a][b]<k` 的边权。",
            "primary_topic": "图论与网络流",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2039H2": {
            "statement_brief": "给定一个数组。一次操作是在 n*n 网格中从左上走到右下，每进入格子 (i,j) 就交换 a_i 和 a_j；要求用不超过 n+4 次这种行走把数组排成非降序。",
            "transformed_statement": "把题目先看成：每条路径不是普通移动，而是在数组上批量执行一组可设计的交换；关键是构造少量路径来模拟分块排序。",
            "key_observations": [
                "简单版瓶颈是每轮奇偶排序后都要额外把最小值调回 a_1。",
                "把值按大小分成小半 S 和大半 B 后，可以先构造出 [S...S,B...B] 的形态。",
                "在 [S...S,B...B] 与 [B...B,S...S] 来回切换时，只需要分别对 B 段和 S 段做奇偶排序。",
                "路径 (1,p1)->(2,p1)->(2,p2)->... 可以近似实现 swap(a_1,p1), swap(a_2,p2), ... 这一串指定交换。",
            ],
            "solution_brief": "关键观察：别把一次 walk 当成单个交换，它能沿路径安排一批指定位置交换。先用少数路径把数组按排名分成前半小值、后半大值；随后两轮从左到右的路径过程分别只让大值段、小值段参与奇偶排序，交换过程中小值和大值整体互换位置。奇数 n 只需额外两次调整，最终总操作数控制在 n+4。",
            "primary_topic": "构造与贪心",
        },
        "2031F": {
            "statement_brief": "交互题。隐藏一个偶数长度排列，每次询问一个偶数长度子序列会返回其中两个中位数的值；要求 80 次询问内找出原排列中两个中位数的位置。",
            "transformed_statement": "把题目先看成：询问“删掉两个位置后的全体元素”可以反推出这两个被删位置相对中位数区间的位置类型。",
            "key_observations": [
                "若删掉 i,j 后返回 n/2 与 n/2+1，说明被删的两数一低一高，且都不是中位数。",
                "拿到一低一高的两个辅助位置 x,y 后，询问 [x,y,i,j] 就能判断 i,j 中是否含有目标中位数。",
                "随机删两个位置有约一半概率得到一低一高；确定性做法则把位置成对分类为低低、高高、低高。",
                "找出含中位数的候选对后，只剩常数种组合，用补集询问确认答案。",
            ],
            "solution_brief": "关键观察：强询问是“除了两个位置都问”。先找一对确定不是中位数、且一低一高的辅助位置；之后把其它位置两两分组，询问 [x,y,i,j]，返回值是否包含 n/2 或 n/2+1 就暴露了该组是否藏着下中位数或上中位数。最后枚举两个候选组里的常数种位置组合，用删掉候选补集后的返回值确认。",
            "primary_topic": "交互",
        },
        "2030C": {
            "statement_brief": "给定一个 0/1 布尔串，两人轮流在相邻布尔值之间填 and 或 or；and 优先于 or 计算。Alice 想让最终表达式为真，Bob 想让它为假。",
            "transformed_statement": "把题目先看成：Alice 需要造出一个两侧被 or 隔开的真块，因为所有 and 会先被算掉，最后 or 才合并。",
            "key_observations": [
                "首位或末位为 1 时，Alice 第一手在它旁边放 or，立刻能保住一个真块。",
                "存在相邻两个 1 时，Alice 可以先在一侧放 or；Bob 即使卡中间，两个 1 的 and/or 结果仍为真，Alice 下一手补另一侧。",
                "若 1 不在端点且没有相邻 1，Bob 总能在 Alice 放出的 or 旁边补 and，把该真块压成假。",
            ],
            "solution_brief": "关键观察：获胜条件只有两类：端点有 1，或存在连续两个 1。前者第一手直接在端点旁放 or；后者围绕这一对 1 两侧放 or，可以形成稳定的真子表达式。其余情况下每个 1 都孤立且不在端点，Bob 对 Alice 的每次 or 都在对应 1 的另一侧放 and，使该局部表达式最终变假。",
            "primary_topic": "博弈",
        },
        "2028F": {
            "statement_brief": "给定数组 a 和目标 m，在相邻数之间填加号或乘号，乘法优先，判断能否让表达式等于 m；内存限制很紧。",
            "transformed_statement": "把题目先看成：表达式是若干连续段乘积的和，DP 只需要记录当前能凑出的和，并按最后一段乘积往前扩。",
            "key_observations": [
                "a_i=0 时，任意后缀乘起来都能贡献 0，因此只需维护历史 DP 的前缀或。",
                "a_i=1 时，最后一个 1 可以接到前段乘积里，也可以作为新加数，相当于状态或上左移一位。",
                "a_i>1 时，最后一段连续乘积一旦超过 m 就不用再扩；这种数最多往前看 log m 个。",
                "所有 j 的转移可以用 bitset 批量做，空间只保留最近 log m 个关键位置和零前缀信息。",
            ],
            "solution_brief": "关键观察：不要存完整 n*m 表。设 bitset 表示处理到当前位置可达的和。遇到 0，用历史可达状态的前缀或处理“乘出 0 的后缀”；遇到 1，用当前 bitset 与左移一位合并；遇到大于 1 的数，只枚举最后一段乘积，乘积超过 m 立即停止。因为大于 1 的乘积长度最多 log m，只需滚动保存这些关键 bitset，空间降到 O(m log m / w)。",
            "primary_topic": "动态规划与状态设计",
        },
        "2024A": {
            "statement_brief": "Alice 有 a 枚硬币。盈利存款原本至少要 b 枚才能开；若先往非盈利存款放 x 枚，盈利存款门槛会降低 2x，但这 x 枚不能再放入盈利存款。求最多能放入盈利存款多少枚。",
            "transformed_statement": "把题目先看成：选 x 后剩余硬币是 a-x，新的门槛是 b-2x，只需让剩余硬币达到新门槛。",
            "key_observations": [
                "可开盈利存款的条件是 a-x >= b-2x。",
                "化简后只需要 x >= b-a；如果 a 已经不少于 b，则 x=0 最优。",
                "为了让最后放入盈利存款的钱最多，x 应取满足条件的最小非负值。",
            ],
            "solution_brief": "关键观察：非盈利存款每放 1 枚虽然损失 1 枚可用硬币，却让门槛下降 2 枚，净效果是把缺口缩小 1。最小需要先放 `max(0,b-a)` 枚；若这个数超过 a 则无法开启，否则答案是 `a-max(0,b-a)`。",
            "primary_topic": "基础实现与模拟",
        },
        "2020F": {
            "statement_brief": "定义深度 d 的除数树：根为 n，每层把当前数的所有除数作为孩子。给 n,k,d，求 sum_{i=1..n} f(i^k,d) mod 1e9+7，其中 f 是叶子数。",
            "transformed_statement": "把题目先看成：一条根到叶路径就是一串 a_0|a_1|...|a_d=n 的除数链；对固定 d，f(n,d) 是乘性函数。",
            "key_observations": [
                "叶子数等于选择 d+1 个数 a_0..a_d，满足 a_d=n 且每一步整除的方案数。",
                "若 n=p^x，问题变成 0<=b_0<=...<=b_d=x 的非降指数序列，方案数为 C(x+d,d)。",
                "不同质因子之间独立，所以固定 d 后 f 是乘性函数。",
                "最终要求的是乘性函数前缀和，可按最小质因子递推，使用类似快速质数计数的分治 DP。",
            ],
            "solution_brief": "关键观察：把除数树路径转成除数链后，质因子完全拆开。对 p^x 的贡献是组合数 C(x+d,d)，对一般数按质因子乘起来。于是 sum f(i^k,d) 变成乘性函数前缀和问题：设 dp(N,p) 表示只使用不小于 p 的最小质因子的数的贡献和，枚举当前质数 p 的幂次并递归到 p 的下一个质数，配合快速质数计数思想做到约 O(n^{2/3})。",
            "primary_topic": "数论与同余",
        },
        "2018C": {
            "statement_brief": "给一棵以 1 为根的树，每次可以删除一个叶子和它的边。求最少删除多少次，使剩余树所有叶子到根的距离相同。",
            "transformed_statement": "把题目先看成：枚举最终叶子深度 d，决定哪些节点必须保留；答案是让被保留节点最多。",
            "key_observations": [
                "若最终叶深为 d，所有深度 d 的节点以及它们的祖先都应该保留。",
                "节点 u 能被保留当且仅当 depth[u] <= d 且 u 的子树最大深度 >= d。",
                "所以每个节点对应一个可保留深度区间 [depth[u], maxDepthInSubtree[u]]。",
                "选择被最多区间覆盖的 d，即保留节点最多，删除数最少。",
            ],
            "solution_brief": "关键观察：不要模拟删叶。先 DFS 求每个节点深度和子树内最大深度；节点 u 在最终深度 d 下存活，当且仅当 d 落在 `[dep[u], mx[u]]`。于是问题变成若干区间选一个点使覆盖数最大，答案为 `n-最大覆盖数`，用差分统计即可。",
            "primary_topic": "树结构",
        },
        "2239E": {
            "statement_brief": "给带点权的无向图，每条边有可通过上限 w 和通过后状态下限 low。起点 s 可任选初始 h，走边要求 h<=w，走后 h=max(h,low)，至少走一条边，最大化终点点权加初始 h。",
            "transformed_statement": "把题目先看成：一条边只在时间区间 [low,w] 内可用；初始 h 就是出发时间，目标是在该时间的连通块里找最大点权。",
            "key_observations": [
                "若把 h 当作时间，边 j 在 low_j 到 w_j 这段时间存在。",
                "移动速度等价于无限快，所以固定时间 h 时，只能在当前动态图的连通块内任选终点。",
                "对每个时间点，需要把连通块最大点权加上时间 h 更新回其中所有起点。",
                "边的存在区间可挂到线段树分治节点，用可回滚并查集维护当前连通块。",
            ],
            "solution_brief": "关键观察：状态更新 `h=max(h,low)` 等价于边只在 `[low,w]` 时间段可走。把所有边按存在区间加入时间线段树，递归到某个时间区间时，把完全覆盖该区间的边并入 DSU，并维护每个连通块的最大点权。叶子时间 h 处，对每个含边连通块用 `maxVal+h` 更新其中点的答案；实现上递归时压缩端点代表元、下传最大值和懒标记，复杂度 O(m log m)。",
            "primary_topic": "图论与网络流",
        },
        "2237I2": {
            "statement_brief": "给一棵有固定儿子顺序的有根树，非根点颜色可为 0/1 或被限制。颜色 0 类似 DFS，颜色 1 类似 BFS；统计所有合法染色能产生多少种不同遍历序。",
            "transformed_statement": "把题目先看成：不同染色可能产生同一遍历序，必须把会被等价消去的坏链规范化后再计数。",
            "key_observations": [
                "I1 的结论是坏链上的 1 可以被改成 0 而不改变遍历序；困难版有强制 1，不能直接全改。",
                "定义本质距离：先把所有坏链上的 1 都视作 0，再数根到该点路径上的 1 个数。",
                "两个染色的所有本质距离相同，则遍历序相同；否则遍历序不同。",
                "没有强制 1 的坏链，或与上方坏链含有同一组强制 1 的坏链，都是二阶坏链，可以删去作为规范化。",
            ],
            "solution_brief": "关键观察：计数对象不是染色本身，而是染色诱导的本质距离。先在每个子树中抽出可能的坏链；若一个坏链不含强制 1，或和最近的上方坏链含同一组强制 1，它不会产生新的遍历序，称为二阶坏链。于是答案等于“不含二阶坏链”的染色数。DP 沿 I1 的子树合并做，但额外区分当前最高坏链以及已经确定含二阶坏链的状态，最后丢掉会产生二阶坏链的部分。",
            "primary_topic": "树结构",
        },
        "2237E": {
            "statement_brief": "给排列 a 和带空位的序列 b，要求补成一个排列，使 b 与 a 可交换，即 a_{b_i}=b_{a_i}；若可行，输出字典序最小补全。",
            "transformed_statement": "把题目先看成：能与 a 交换的排列，必须把 a 的每个环映射到另一个等长环，并在环内保持同一个循环位移。",
            "key_observations": [
                "先把 a 分解成若干环；不同长度的环不能互相映射。",
                "b 中已知值会强制源环映射到某个目标环，并强制一个环内位移。",
                "同一源环若被强制到不同目标环、不同位移，或目标环长度不等，则无解。",
                "剩余未匹配环按长度分组；为字典序最小，源环按最左位置从小到大匹配目标环最小可用值。",
            ],
            "solution_brief": "关键观察：交换关系把问题降到环之间的匹配。对每个源环检查 b 的已知位置，确定目标环和循环偏移，冲突立即无解；已被占用的目标环不能再用。剩余环只在相同长度桶内自由匹配，按源环最早出现位置从小到大，贪心选目标环中最小的首元素，最后按确定的偏移填回所有空位。",
            "primary_topic": "图论与网络流",
        },
        "2223F": {
            "statement_brief": "有 m 类字符，第 i 类有 n_i 个、每个可染 c_i 种颜色；每次可删除 d_i 个连续同类同色字符。统计能被删空的彩色字符串数。",
            "transformed_statement": "把题目先看成：若 n_i 不是 d_i 的倍数则无解；否则每次删除的一组字符像一组括号，组内 d_i-1 个空隙可以嵌套其它可删结构。",
            "key_observations": [
                "删除顺序不影响合法性，可以用栈过程判定字符串能否被删空。",
                "一次删除 d_i 个同类同色字符，对应一个外层括号结构，中间有 d_i-1 个可嵌套间隙。",
                "相邻栈层不能是同类同色，因此计数时先算括号结构的合法染色概率，再乘上各类颜色总选择。",
                "设 F_i 为外层类型 i 的生成函数，可得到 F_i=x_i/(1-(sum F)-q_i F_i)^{d_i-1}，再用多元拉格朗日反演提系数。",
            ],
            "solution_brief": "关键观察：先把删字符过程翻译成带类型的括号树，而不是直接数串。每个类型 i 的一个删除块提供 d_i 个同色同类端点和 d_i-1 个子结构间隙；为了避免和栈下方完全同类同色，需要在生成函数里扣掉 q_i F_i。得到方程组后套多元拉格朗日反演，把答案化成独立变量乘积与一个行列式因子；后续再引入辅助变量统计指数和，用分治/卷积完成总系数计算。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2217D": {
            "statement_brief": "给二进制数组和若干特殊位置，特殊位置初值相同。一次操作必须选择包含至少一个特殊位置的区间并翻转，求把所有数变回特殊位置初值的最少操作数。",
            "transformed_statement": "把题目先看成：翻转区间只会改变两个边界；特殊位置把所有边界分成若干区域，一次操作只能配对不同区域的两个边界。",
            "key_observations": [
                "把目标值相同的位置记为 1、不同记为 0，并在两端补目标值；相邻不同处就是需要消掉的边界。",
                "翻转 [l,r] 会切换 l-1 和 r 两个边界。",
                "区间必须包含特殊位置，等价于被配对的两个边界之间至少跨过一个特殊位置，也就是来自不同区域。",
                "若总边界数为 S、单个区域最多为 X，则答案是 max(S/2, X)。",
            ],
            "solution_brief": "关键观察：每次操作最多消掉两个边界，但这两个边界不能在同一特殊位置分隔出的区域内。若没有区域边界数超过一半，就能把所有边界两两跨区域配对，代价 S/2；若某个区域有 X>S/2 个边界，先用其它 S-X 个边界与它配对，剩下 2X-S 个只能单独处理，总代价 X。因此线性统计每个区域边界数，输出 `max(S/2,X)`。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2207H1": {
            "statement_brief": "交互题。隐藏函数由按顺序出现的变量和若干 min/max 组成，每个变量恰好出现一次；通过询问函数值还原整棵表达式树，并回答后续求值。",
            "transformed_statement": "把题目先看成：min/max 表达式在 0/1 输入上等价于 AND/OR 表达式树；先还原布尔树结构，再照原来的 min/max 求值。",
            "key_observations": [
                "相邻同类 min 或 max 节点可以合并，剩下的内部节点会沿根到叶交替出现。",
                "用 0/1 输入询问即可把 max 看成 OR、min 看成 AND。",
                "扫描前缀全 1 和后缀全 1 的临界位置，可判断根节点是 OR 还是 AND。",
                "在已知根为 OR 的情况下，贪心删除左侧输入仍保持输出为 1 的变量，最后一个保留的 1 就给出根的左右分裂点。",
            ],
            "solution_brief": "关键观察：函数还原不是拟合数值，而是还原一棵保持变量顺序的 AND/OR 树。先用前缀、后缀 1 的临界点判断根类型；若根是 AND，就对输入和输出取反转成 OR。根为 OR 时，找出能让左段和右段同时支撑输出 1 的切分点，然后递归处理左右子区间。简单版 n<=70，二次询问量足够。",
            "primary_topic": "交互",
        },
        "2163A": {
            "statement_brief": "给一个数组，两人按位置顺序轮流选择是否交换相邻元素；Souvlaki 可在游戏前任意重排数组，问他能否保证最后数组非降。",
            "transformed_statement": "把题目先看成：Kalamaki 在偶数轮能控制一对固定相邻位置；只要这两个数不同，他总能让最终数组失序。",
            "key_observations": [
                "偶数轮位置 2k 与 2k+1 若不同，Kalamaki 可以根据大小选择换或不换，使该处最终不可能有序。",
                "因此所有偶数轮控制的相邻对必须相等。",
                "在这个前提下，Souvlaki 只需要把数组预先排序，再检查排序后 a_2=a_3、a_4=a_5 等配对条件。",
            ],
            "solution_brief": "关键观察：对手能动的偶数边必须被“消毒”为两个相等元素，否则无论当前大小关系如何，对手都有办法留下逆序。Souvlaki 最优预处理就是排序；排序后检查每个偶数位置 i 的 a_i 是否等于 a_{i+1}。全部满足则 YES，否则 NO。",
            "primary_topic": "博弈",
        },
        "2134C": {
            "statement_brief": "给非负数组，每次可把某个元素减一。要求所有长度至少 2 的子数组中，原数组偶数下标元素和不少于奇数下标元素和，求最少减少次数。",
            "transformed_statement": "把题目先看成：只需要约束形如 odd-even-odd 的长度 3 片段；其它更长片段会由这些局部约束相加推出。",
            "key_observations": [
                "偶数位置永远不该被减少，因为它们只出现在约束左侧，减少会让条件更难满足。",
                "若所有奇-偶-奇三元片段都满足 a_i+a_{i+2}<=a_{i+1}，则所有奇端点长区间也满足；其它区间更弱。",
                "于是只需给每个奇数位置保留尽量大的最终值，同时不破坏左右相邻三元约束。",
                "从左到右贪心确定奇数位置保留值即可，因为它只影响左、右两个相邻约束。",
            ],
            "solution_brief": "关键观察：全局子数组条件可以压成局部三元条件。保留所有偶数下标值不变；对奇数下标 i，最终值最多不能超过原值、左侧偶数剩余容量、右侧偶数值。按从左到右计算这个最大可保留值，减少量累加就是答案。",
            "primary_topic": "构造与贪心",
        },
        "2120F": {
            "statement_brief": "给 k 个同一点集上的图，问是否存在若干原图 H_i，使给出的 G_i 都是对应 H_i 的最小阶压缩图，并且同一个点在所有图中的压缩类型保持一致。",
            "transformed_statement": "把题目先看成：每个点要被判为“独立集型”或“团型”；图中可继续合并的孪生点会给这种二元选择施加限制。",
            "key_observations": [
                "若两个非相邻点开邻域相同，它们不能都代表独立集，否则还能合成更大的独立集，压缩图不是最小。",
                "若两个相邻点闭邻域相同，它们不能都代表团，否则还能合成更大的团。",
                "这些限制分别变成：某些点对不能同时取 0，某些点对不能同时取 1。",
                "跨所有 G_i 收集限制后，就是一个 2-SAT 可满足性问题。",
            ],
            "solution_brief": "关键观察：superb 的最小性只会被两类孪生点破坏。对每个图找 type1：非相邻且开邻域相同，要求二者至少一个是团型；找 type2：相邻且闭邻域相同，要求二者至少一个是独立集型。把所有图的这些二元约束加入 2-SAT，若可满足就存在统一的 H_i 解释，否则不存在。",
            "primary_topic": "图论与网络流",
        },
        "2113A": {
            "statement_brief": "烤炉初始温度为 k，有两种烤串：达到各自最低温度后才能烤，烤完分别降温 x 或 y。每种数量无限，求最多能烤多少串。",
            "transformed_statement": "把题目先看成：只要当前能烤，优先选择降温更小的那种，因为保持更高温度永远不会减少后续选择。",
            "key_observations": [
                "当前温度越高，可烤种类只会更多，不会更少。",
                "因此在两种都可烤时，选择降温较小的一种总不劣。",
                "先尽可能烤降温较小且当前满足门槛的种类，再烤另一种即可。",
            ],
            "solution_brief": "关键观察：这是单调资源消耗问题，贪心按较小降温优先。若两种都能做，降温小的保留了更高温度，后续可行集合包含另一选择后的可行集合。先算第一种能连续烤多少次并更新温度，再算第二种；若降温大小相反，交换两种即可。",
            "primary_topic": "基础实现与模拟",
        },
        "2103C": {
            "statement_brief": "给数组 a 和 k，问能否切成三个非空连续段，使三个段中位数的中位数不超过 k。",
            "transformed_statement": "把题目先看成：至少两个段的中位数要不超过 k；把 <=k 的元素记为 +1，>k 的元素记为 -1，则一个段合格等价于段和非负。",
            "key_observations": [
                "三个段的中位数再取中位数 <=k，等价于三段里至少两段合格。",
                "段中 <=k 的数量不少于 >k 的数量，正好等价于 +1/-1 段和 >=0。",
                "只需检查三种组合：前+中、中+后、前+后。",
                "前+中可用前缀和与后缀最大前缀和线性判定；中+后对称；前+后只需最短合格前缀和最短合格后缀不相交。",
            ],
            "solution_brief": "关键观察：中位数条件可以完全二值化。转换成 +1/-1 后，问题变成切三段使至少两段和非负。扫描前缀，若某个前缀和非负且后面存在更大的前缀和，就能让前段和中段合格；反向再做一次处理“中段+后段”。最后单独检查最短合格前缀与最短合格后缀之间是否还能留出非空中段。",
            "primary_topic": "构造与贪心",
        },
        "2101D": {
            "statement_brief": "给一个排列，统计有多少非空子数组满足 LIS 长度 + LDS 长度 = 子数组长度 + 1。",
            "transformed_statement": "把题目先看成：合法子数组中，最长升子序列和最长降子序列必须恰好共享一个元素，其它元素分别落到升链或降链上。",
            "key_observations": [
                "LIS 和 LDS 不可能共享两个元素；若完全不共享，长度和又不够，因此必须恰好共享一个点。",
                "围绕共享点，左侧较小值和右侧较大值要形成升序，左侧较大值和右侧较小值要形成降序。",
                "合法性对取子数组是单调的：一个 cute 子数组的内部子数组仍 cute。",
                "对每个中心 i 求最大合法区间 [L_i,R_i]，最后统计被这些区间覆盖的子数组数量。",
            ],
            "solution_brief": "关键观察：先刻画 cute 子数组的形状，而不是直接维护 LIS/LDS。由唯一共享点得到两边的相对单调结构；因此对固定 i，可以找第一个破坏相邻两同奇偶链大小关系的位置，得到 R_i，L_i 对称。R_i 满足 `R_i=min(R_{i+1}, f(i))`，f(i) 可用单调栈或线段树找。拿到所有 [L_i,R_i] 后，统计所有被至少一个区间包含的子数组。",
            "primary_topic": "数据结构",
        },
        "2056A": {
            "statement_brief": "一个 m*m 印章每次向右 x_i、向上 y_i 后盖章，所有 x_i,y_i 都在 1 到 m-1 之间；求最终连通图形周长。",
            "transformed_statement": "把题目先看成：每次新正方形都与上一个在横向和纵向上重叠，因此外轮廓宽度和高度只由首个左下角与最后一个右上角决定。",
            "key_observations": [
                "因为 1<=x_i,y_i<m，相邻两个正方形必然重叠，整体没有断开。",
                "横向跨度为 m 加上从第二次开始的所有 x_i，纵向同理。",
                "外轮廓周长就是 2*(横向跨度+纵向跨度)。",
            ],
            "solution_brief": "关键观察：这题不用算每对正方形重叠边。所有位移都小于边长，图形始终连通且每一步只扩展整体包围区间。横向有效长度为 `m+sum_{i=2..n} x_i`，纵向为 `m+sum_{i=2..n} y_i`，答案为两者之和乘 2。",
            "primary_topic": "几何",
        },
        "2239F": {
            "statement_brief": "边染色有 n 种颜色，合法作品是一棵有根树：相邻两条边颜色不同，且每种颜色在根路径上的最大出现次数落在给定区间内。问非同构合法作品数量的奇偶。",
            "transformed_statement": "把题目先看成：先固定每种颜色的上界 a_i；模 2 下，树计数递推可解释成一个禁止连续选同色的取石游戏。",
            "key_observations": [
                "设 f_{c,a} 为向上边颜色为 c、剩余上界为 a 的树数；模 2 后可把 1 看成先手必胜。",
                "转成游戏后，每次选一个正的 a_i 减一，且不能连续选上一回合同色。",
                "若某个颜色 2a_i>S，先手可一直控制该颜色并获胜；否则双方总能维持无主导颜色，胜负只看 S 奇偶。",
                "一般区间用容斥，在模 2 下 (1+x^k)^2=1+x^{2k}，可不断合并相同二项式因子。",
            ],
            "solution_brief": "关键观察：先把固定上界的树计数变成游戏判定：若最大堆超过总和一半，答案奇偶立刻由主导颜色决定；否则只看总和奇偶。再对每个颜色从 l_i-1 与 r_i 中选上界做容斥，问题剩下若干形如 `1+x^k` 的生成函数乘积。模 2 下相同因子平方会变成 `1+x^{2k}`，不断合并后只剩少量不同因子，用 bitset 做多项式乘法取需要的前若干项。",
            "primary_topic": "组合计数与概率",
        },
        "2190E": {
            "statement_brief": "给部分已知的长度 n 排列 a，要求补成排列 p，使所有连续三元组的中位数互不相同；已知 1 和 n 的位置，求补全方案数。",
            "transformed_statement": "把题目先看成：三元组中位数不重复会强迫同奇偶位置几乎单调，并且偶链与奇链整体只允许两种相对大小关系。",
            "key_observations": [
                "1 和 n 不可能成为任何三元组中位数，因此 f(p) 必须恰好覆盖 2..n-1。",
                "若同奇偶链出现峰 p_{i-2}<p_i>p_{i+2}，则 p_i 必须是 n；谷同理必须是 1。",
                "因此除包含 1 或 n 的位置外，同奇偶下标形成两条单调链。",
                "若一条奇偶链升、另一条降，局部长度 4/5 检查会迫使一整条链的值都小于另一条链。",
            ],
            "solution_brief": "关键观察：重复中位数只可能在相交的长度 3 窗口里产生，所以检查长度 5 的局部结构足够。由局部结构推出：同奇偶位置分别是两条几乎单调的链，且两条链之间只有固定的上下关系。计数时按 1 与 n 的奇偶位置分情况，把未填值分配到两条链上；已知 a_i 变成链上的相对顺序约束，最终用组合数/前缀约束统计可行补全。",
            "primary_topic": "组合计数与概率",
        },
        "2190A": {
            "statement_brief": "二进制串游戏。每次可选择若干下标，使选出的字符序列非增，并把这些位置重排成非降；必须真正改变字符串。不能行动者输，要求判断胜者并给 Alice 的首步。",
            "transformed_statement": "把题目先看成：若字符串未排序，Alice 可以一次选出所有与排序后目标串不同的位置，把整串直接排好。",
            "key_observations": [
                "排好序的二进制串没有合法操作，当前行动者输。",
                "设目标串 t 为所有 0 在前、1 在后；所有不匹配位置中，前半只能是 1，后半只能是 0。",
                "因此这些不匹配位置按原下标读出来一定是若干 1 后接若干 0，满足非增。",
                "对这些位置排序后，刚好把前半多余的 1 和后半多余的 0 交换完。",
            ],
            "solution_brief": "关键观察：未排序时可以一步杀。把 s 排序得到 t；若 s=t，则 Bob 赢。否则 Alice 选择所有 `s_i!=t_i` 的位置，这些字符天然是非增序列，操作后整串变成 t，Bob 无法继续行动，所以 Alice 赢并输出这些位置。",
            "primary_topic": "博弈",
        },
        "2188B": {
            "statement_brief": "一排座位已有一些学生，且没有相邻学生。要继续安排学生直到无法再安排，同时希望最终学生总数最少，求这个最小总数。",
            "transformed_statement": "把题目先看成：每段连续空位独立处理；新增一个学生最多覆盖自己和左右相邻共 3 个空位，使这些位置不能再坐人。",
            "key_observations": [
                "被两个已有 1 夹住的长度 len 空段，最少需要 floor(len/3) 个新学生就能堵满。",
                "靠边空段少了一个已有 1 边界，需要把长度额外加 1 再除以 3。",
                "全串都是 0 时两侧都没有边界，相当于长度额外加 2。",
                "已有的 1 也计入最终总人数。",
            ],
            "solution_brief": "关键观察：按连续 0 段相加。给字符串两端补虚拟 1；每遇到一段 0，根据它是否贴原串边界给长度加上 0、1 或 2，再贡献 `floor(adjusted_len/3)` 个新学生。答案还要加上原来已有的 1 的数量。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2153D": {
            "statement_brief": "给一个环形数组，每次可把某个数加一或减一。要求改成一个环形数组，使每个位置至少有一个相邻位置与它相等，求最小总代价。",
            "transformed_statement": "把题目先看成：最终数组由若干等值连续块组成，每个块长度至少为 2；而任意长度至少 2 的块都能拆成长度 2 或 3 的小块。",
            "key_observations": [
                "nice 条件等价于每个元素属于某个长度至少 2 的等值块。",
                "所有长度至少 2 的块都可由 2 和 3 拼出，因此只需考虑末块长度为 2 或 3。",
                "线性数组上有转移 dp[i]=min(dp[i-2]+两数改相等代价, dp[i-3]+三数改相等代价)。",
                "环上块长最多只需跨过切口 2 或 3 个位置，所以试 3 个相邻切口即可覆盖最优情况。",
            ],
            "solution_brief": "关键观察：不要枚举最终块长。因为每个合法块都能拆成 2/3 小块，线性 DP 只看最后 2 个或 3 个数改成同值的最小代价；两数代价是差的绝对值，三数代价是最大值减最小值。为处理环，只需旋转数组试三种切口后跑同一 DP，取最小值。",
            "primary_topic": "动态规划与状态设计",
        },
        "2143D1": {
            "statement_brief": "给序列 a，统计多少子序列的逆序图可以二染色；逆序图中 i<j 且 b_i>b_j 时连边，答案包含空子序列。",
            "transformed_statement": "把题目先看成：逆序图可二染色等价于所选子序列的最长下降子序列长度不超过 2。",
            "key_observations": [
                "若存在长度 3 的下降子序列，三个点两两成逆序边，形成三团，无法二染色。",
                "若最长下降子序列长度不超过 2，可按“从该位置开始的最长下降长度”给颜色，不会有同色逆序边。",
                "于是只需计数 LDS<=2 的子序列。",
                "简单版用 DP 维护当前子序列最大值 m，以及已经被更大值压过的最大值 mp；若新数小于 mp 就会形成长度 3 下降链，禁止转移。",
            ],
            "solution_brief": "关键观察：图染色条件转成序列条件。处理 a_i 时，可以不选；若选它，若 a_i>=m 则更新最大值，若 mp<=a_i<m 则更新 mp，若 a_i<mp 则会出现 m>mp>a_i 的下降三元组，不能选。三维状态数 O(n^3)，符合 简单版限制，最后求和所有合法状态。",
            "primary_topic": "动态规划与状态设计",
        },
        "2140C": {
            "statement_brief": "数组函数为交错和加累计代价。两人轮流选择结束，或交换一对位置并把距离加入代价；Alice 最大化，Bob 最小化，求最优最终值。",
            "transformed_statement": "把题目先看成：Bob 若交换，Alice 下一步可交换同一对恢复数组并额外增加代价，所以 Bob 最优第一步结束；只需分析 Alice 首步是否交换。",
            "key_observations": [
                "Bob 的任何非结束交换都会被 Alice 对称反制，且总代价增加，对 Bob 不利。",
                "因此游戏只剩 Alice 第一手：结束或交换一对，然后 Bob 结束。",
                "同奇偶位置交换不改变交错和，只增加距离。",
                "异奇偶位置交换的增量为距离加上两倍的值差，可用奇偶前缀最小维护最大收益。",
            ],
            "solution_brief": "关键观察：长博弈被对称反制压成一回合优化。先算原交错和；Alice 枚举一次交换的最大增益。同奇偶交换只看最远距离，异奇偶交换把公式写成 `|i-j|+2*(a_even-a_odd)`，分别维护奇偶位置上的最小表达式即可线性求最大值。",
            "primary_topic": "博弈",
        },
        "2135C": {
            "statement_brief": "给连通无向图，部分点权缺失。要求任意两点间所有简单路径的点权异或和相同，统计缺失点权赋值数。",
            "transformed_statement": "把题目先看成：同一个简单环上的所有点权会被强制相等；若环长为奇数，这个共同值还必须为 0。",
            "key_observations": [
                "在一个环上任选两点，两条简单路径异或值必须相同，推出去掉这两端后的任意等长替换异或不变。",
                "比较只差一个点的集合，可推出环上任意两点权相等。",
                "若环长为奇数，相同点权在整环约束下只能为 0。",
                "共享环关系等价于处在同一个边双连通分量；不同边双分量互不影响。",
            ],
            "solution_brief": "关键观察：平衡条件的约束只沿环传播。先用 Tarjan 分出边双连通分量；每个分量内所有点权必须相同。若分量含奇环，用二染色检测失败，此时共同值只能是 0；若没有奇环，共同值可为任意 0..V-1。再结合已知点权检查冲突，每个分量贡献 0、1 或 V，整体相乘。",
            "primary_topic": "图论与网络流",
        },
        "2124C": {
            "statement_brief": "原数组相邻整除。某个未知正整数 x 被乘到原数组的某个子集上，得到 b；保证有解，要求输出任意可能的 x。",
            "transformed_statement": "把题目先看成：相邻 b_i 到 b_{i+1} 的整除断点，只可能由左边被额外乘了 x 而右边没乘造成，因此这些断点给出 x 的必要因子。",
            "key_observations": [
                "对每对相邻元素，若要恢复 a_i|a_{i+1}，x 必须补掉 b_i 中不能整除 b_{i+1} 的那部分。",
                "这个必要部分是 b_i/gcd(b_i,b_{i+1})。",
                "把所有相邻对的必要部分取最小公倍数即可。",
                "题目保证有解时，这个最小公倍数作为 x 已经足够，不需要恢复具体原数组。",
            ],
            "solution_brief": "关键观察：只看相邻断点。对每个 i，把 `need=b_i/gcd(b_i,b_{i+1})` 纳入答案的 lcm；直观上这是左项多出来、必须被 x 覆盖的因子。若两边同乘或都没乘，x 无影响；若只有右边同乘，取更大的 x 也不会修复额外问题。由于题目保证存在答案，输出这些 need 的 lcm 即可。",
            "primary_topic": "数论与同余",
        },
        "2124A": {
            "statement_brief": "可删除数组若干元素并保留相对顺序，问能否让剩余非空数组与其排序后数组每个位置都不同；若能，输出任意方案。",
            "transformed_statement": "把题目先看成：若原数组整体非降，删完后仍非降，不可能错位；若存在逆序对，取这两个数就已经是长度 2 的错位数组。",
            "key_observations": [
                "删除不会改变剩余元素的相对顺序，所以非降数组的任何子序列仍非降。",
                "非降数组排序前后完全一样，不可能成为 derangement。",
                "若存在 i<j 且 a_i>a_j，保留 [a_i,a_j] 后排序为 [a_j,a_i]，两个位置都不同。",
            ],
            "solution_brief": "关键观察：答案只取决于是否存在逆序对。扫描找任意 a_i>a_j；找到就输出 YES、长度 2 和这两个数。若找不到，原数组非降，所有删除后的数组也非降，排序前后相同，因此输出 NO。",
            "primary_topic": "基础实现与模拟",
        },
        "2107C": {
            "statement_brief": "给带缺失位置的数组和目标 k，缺失位置可填到 1e18 量级。要求填数后最大子段和恰好为 k，或报告无解。",
            "transformed_statement": "把题目先看成：除一个缺失位置外，其它缺失位置都填成极小值，用唯一保留的位置把经过它的最大子段和调到 k。",
            "key_observations": [
                "先把所有缺失位置当成负无穷；若仅由已知位置形成的最大子段和已经大于 k，则无解。",
                "若没有缺失位置，则只能检查原最大子段和是否等于 k。",
                "有缺失位置且已知部分不超过 k 时，一定可构造。",
                "选一个缺失位置 pos，令左侧最大后缀为 L、右侧最大前缀为 R，填入 k-L-R 即可。",
            ],
            "solution_brief": "关键观察：把缺口变成一个可调旋钮。所有未选缺失位填极小值，保证跨过它们的子段不会参与最大值；选定 pos 后，包含 pos 的最大子段和就是 `L+x+R`。令 `x=k-L-R`，则经过 pos 的最好子段正好为 k，而不经过 pos 的子段前面已验证不超过 k。",
            "primary_topic": "构造与贪心",
        },
        "2096H": {
            "statement_brief": "给 n 个区间 [l_i,r_i] 和位数 m。对每个异或值 x，统计从每个区间取一个数且总异或为 x 的方案数 f_x，再计算加权后的整体异或输出。",
            "transformed_statement": "把题目先看成：区间选择多项式之间做异或卷积；用沃尔什变换把卷积变成逐点乘法，再利用区间前缀和的特殊结构避免逐区间做完整变换。",
            "key_observations": [
                "每个区间对应多项式 A_i=x^{l_i}+...+x^{r_i}，目标是所有 A_i 的异或卷积。",
                "沃尔什变换下，异或卷积变成逐点乘积。",
                "变换值是符号函数 s(k,j)=(-1)^{popcount(k&j)} 在区间上的和，可用最低置位把完整周期全部抵消。",
                "每个区间的变换值可压成两个单项式的形式，之后合并同幂项并用 SOS DP 求所有点值。",
            ],
            "solution_brief": "关键观察：难点不是会用 FWHT，而是快速求每个区间在每个频率 k 下的变换值。对 `sum_{j<=r} s(k,j)`，按 k 的最低置位分块，完整长度 `2^{p+1}` 的块贡献为 0，只剩最后一小段；于是区间贡献能写成依赖 `k>>(p+1)` 的两个符号项。把每个区间归一成 `a+b*x^c`，相同 c 的项先合并，最后用 SOS DP 计算所有频率上的乘积，再逆变换得到 f_x。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2061G": {
            "statement_brief": "交互题。任意两人关系可被询问为朋友或非朋友，且交互器可自适应。要求在不超过 n 次询问内，保证找到尽量多对同色关系的配对。",
            "transformed_statement": "把题目先看成：完全图边被染成两色，要在少量询问下构造一组同色匹配；保证规模的上限和构造都围绕三人一组。",
            "key_observations": [
                "存在构造使任一颜色的最大匹配都不超过 floor((n+1)/3)，所以 k 不可能更大。",
                "维护一条同色链；新点接到链尾若同色就延长链。",
                "若颜色不同，则链尾两个点加新点形成一个混色三元组，可以从中保证取出一条所需颜色的匹配边。",
                "最终由若干混色三元组和一条同色链组成，三元组每个贡献一对，链贡献 floor(len/2) 对。",
            ],
            "solution_brief": "关键观察：查询过程把点分解成可控的三元组。维护一条红链或蓝链，加入新点只问它和链尾的关系；同色则加入链，否则把链尾两个点与新点打包成混色三元组并从链中移除两个点。n-1 次询问后，所有点被分成若干三元组和一条同色链，从每个三元组取一条目标颜色边、从链中相邻配对，即可达到 floor((n+1)/3) 的最优保证。",
            "primary_topic": "交互",
        },
        "2057B": {
            "statement_brief": "函数 f(a) 表示每次选一段并删掉其中最小值的所有出现位置，直到数组为空的最少操作数。最多改 k 个元素，求能达到的最小 f。",
            "transformed_statement": "把题目先看成：f(a) 其实就是数组不同值的数量；修改元素的目标是尽量消掉出现次数少的值。",
            "key_observations": [
                "每次直接选整个数组删除当前全局最小值，最终每个不同值正好删一次。",
                "任何操作一次只能删除一种值，所以 f(a) 不可能小于不同值个数。",
                "修改一个出现次数为 c 的值族，需要花 c 次才能完全并入别的值。",
                "为了用 k 次修改消掉最多值，应从出现次数最小的值族开始删。",
            ],
            "solution_brief": "关键观察：原来的区间删除定义只是不同值计数。统计每个值出现次数并排序，从小到大用 k 消掉整个值族；每消掉一族，不同值数量减一。最后至少保留一种值，所以答案为剩余不同值数量。",
            "primary_topic": "构造与贪心",
        },
        "2055C": {
            "statement_brief": "网格原本所有行和所有列的和都相等；一条从左上到右下的路径被清零。要求给路径格重新赋值，恢复这个性质。",
            "transformed_statement": "把题目先看成：统一目标行/列和可以直接取 0；沿路径走时，每一步都会离开某一行或某一列，此时该行/列只剩当前路径格未定。",
            "key_observations": [
                "若公共和为 S，总行和为 nS，总列和为 mS；为保证所有 n,m 都可行，取 S=0 最稳。",
                "沿路径遇到 R 时，当前列之后不会再被路径访问，可立刻把当前格设成该列和为 0 所需的值。",
                "遇到 D 时同理，当前行之后不会再被访问，可立刻补成行和 0。",
                "最后右下角用最后一行或最后一列补值，另一边会因总和为 0 自动满足。",
            ],
            "solution_brief": "关键观察：不用解线性方程组。目标设为所有行列和都为 0；从左上沿路径处理，若下一步向右，就说明当前列的路径变量到此结束，填当前格为该列现有和的相反数；若下一步向下，则填成当前行现有和的相反数。最后一个格子按最后一行补齐即可，最后一列由总和守恒自动为 0。",
            "primary_topic": "构造与贪心",
        },
        "2053F": {
            "statement_brief": "矩阵中元素属于 1..k，部分为空。填空后，beauty 是相邻两行中相同数字出现次数乘积的总和；求最大 beauty。",
            "transformed_statement": "把题目先看成：每一行的所有空位在某个最优解中可以填成同一个数字，于是行与行之间只剩“本行空位统一填 j”的 DP。",
            "key_observations": [
                "固定上一行和下一行时，本行一个新填数字 u 的贡献只取决于上下两行 u 的出现次数；所有空位都选贡献最大的 u 不劣。",
                "设 dp[j] 表示当前行空位统一填 j 时，处理到这一行的最大额外贡献。",
                "对相邻两行，只有在这两行真实出现过的数字需要单独更新；其它数字的转移形式相同。",
                "大量相同转移可表示成全局标记 `x -> max(A, x+B)`，标记可以常数合成。",
            ],
            "solution_brief": "关键观察：先证明一行的空位可统一填同一个值，避免每个空位独立爆炸。朴素 DP 是行数乘 k；但第 i 行和第 i-1 行实际出现的不同数字总共 O(m)，只有这些 j 的 d_{i,j} 非零，需要精确转移。其它 j 共享同一个 `max(全局最优, dp_j+常数)` 形式，用可合成懒标记维护，逐行只暴力更新出现过的数字，总复杂度 O(nm)。",
            "primary_topic": "动态规划与状态设计",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2049F": {
            "statement_brief": "维护数组的若干单点加法更新。每次更新后，求最长连续子数组，使其 MEX 减去所有元素按位或恰好等于 1。",
            "transformed_statement": "把题目先看成：好子数组必须恰好包含 0..m 的所有数，且最大值 m 必须形如 2^k-1。",
            "key_observations": [
                "设子数组最大值为 m，按位或至少为 m；若 MEX-OR=1，则 MEX 至少为 m+1。",
                "MEX 不可能超过 m+1，所以必须包含 0..m，且 MEX=m+1。",
                "0..m 的按位或等于 m 当且仅当 m 的低位全为 1，即 m=2^k-1。",
                "正向更新难维护，倒序看更新就变成单点值减少，某个 k 下只会把位置加入合法组件或合并组件。",
            ],
            "solution_brief": "关键观察：先把 good 条件刻画死：最大值只能是 `2^k-1`，并且 0..2^k-1 都要在子数组中出现。对每个 k，只看值不超过 `2^k-1` 的连续段，段内不同值数量达到 `2^k` 就是候选答案。把所有更新倒过来处理，位置只会从不可用变可用或并入相邻组件；组件内用小并大维护值频次和长度，全局维护满足条件的最大长度。",
            "primary_topic": "数据结构",
        },
        "2034C": {
            "statement_brief": "网格中每个格子有固定方向或未知方向，沿方向移动，出界则逃脱，进环则被困。可以给未知格填方向，最大化会被困的起点数。",
            "transformed_statement": "把题目先看成：先找出无论怎么填都一定能逃出去的格子，剩下格子都可以安排成走向某个环。",
            "key_observations": [
                "固定方向且直接或间接走出边界的格子必然不能算被困。",
                "在反向图上从边界外开始扩展，可以找出所有确定会逃脱的固定方向格。",
                "未知格如果四个邻居都已经会逃脱，那么它无论指向哪里也会逃脱。",
                "其余未知格至少能指向一个不会逃脱的邻居，可被安排进环或通向环。",
            ],
            "solution_brief": "关键观察：最大化被困数等价于最小化必逃格。先按固定箭头建反向边，从虚拟边界做搜索，标出所有能到边界的格子。然后检查 `?`：若上下左右全是已逃脱区域，则它也必逃；否则可把它指向未逃脱区域，使其被困。答案为总格子数减必逃格数量。",
            "primary_topic": "图论与网络流",
        },
        "2031C": {
            "statement_brief": "给 n 个位置填馅料编号。每种编号要么不用，要么至少出现两次；任意两个相同编号的位置距离必须是完全平方数。要求构造或判无解。",
            "transformed_statement": "把题目先看成：偶数 n 可用相邻成对解决；奇数 n 必须有某个编号出现至少三次，而三个两两平方距离的位置最短跨度是 25。",
            "key_observations": [
                "距离 1 是平方数，所以偶数 n 直接填 1,1,2,2,...。",
                "奇数 n 的总出现次数为奇数，必有一种馅料出现至少三次。",
                "若位置 x<y<z 同色，则 y-x、z-y、z-x 都要是平方数；最小正解为 9、16、25。",
                "因此 n<=25 的奇数无解；n=27 可硬构造，之后追加相邻对即可。",
            ],
            "solution_brief": "关键观察：奇数情况不能靠普通配对，必须制造三次出现的颜色。三个同色位置的两段距离和总距离都为平方数，最短只能是 9、16、25，所以长度不超过 25 无解。题解给出 n=27 的固定模板；更大的奇数在模板后面继续补相邻相同对，偶数则全用相邻对。",
            "primary_topic": "构造与贪心",
        },
        "2030E": {
            "statement_brief": "数组 b 的分数定义为把元素划分成若干多重集合后，各集合 MEX 之和的最大值。给数组 a，求所有非空子序列分数之和。",
            "transformed_statement": "把题目先看成：一个子序列的分数只由每个值的出现次数决定，且等于 f_0 + min(f_0,f_1)+min(f_0,f_1,f_2)+...。",
            "key_observations": [
                "每构造一个 MEX 至少为 j+1 的集合，都要消耗一个 0..j。",
                "因此能贡献到第 j 层的集合数正是 min(f_0..f_j)。",
                "对子序列求和时，只需要按值从小到大维护当前前缀出现次数最小值。",
                "状态 j 只会落在 1..当前值频次，总状态规模对所有值求和为 O(n)。",
            ],
            "solution_brief": "关键观察：先把“最优划分”变成频次数组公式。对子序列 DP，令 dp[i][j] 表示只考虑值 0..i，当前前缀最小出现次数为 j 的子序列数。加入值 i 时，若选了恰好 j 个它，可能把最小值降到 j；若选了不少于 j 个，则最小值保持。用组合数和后缀和转移，并在每个 i 把 `j*方案数*后续任意选择数` 加入答案。",
            "primary_topic": "组合计数与概率",
        },
        "2023D": {
            "statement_brief": "有若干游戏，每个游戏赢率 p_i%、奖金 w_i；选择一个集合，只有全部赢才拿到总奖金，最大化期望，且每个单游戏满足 w_i*p_i<=2e5。",
            "transformed_statement": "把题目先看成：如果选了任何非百分百胜率游戏，那么最优集合的总奖金有一个常数上界，因此可以做按奖金和的背包。",
            "key_observations": [
                "若某个 p<100 的游戏留在集合中，删除它后期望不应变大，这会推出当前其它总奖金 W 不能太大。",
                "由 w_i*p_i<=2e5 可得含非满概率游戏的最优总奖金不超过约 2e5*100/99。",
                "同一概率 p 下，最优只会取奖金从大到小的一个前缀。",
                "对固定 p，前缀长度也有上界，大约 100/(100-p)，因此总候选数很小。",
            ],
            "solution_brief": "关键观察：概率乘积让“大量低概率游戏”不可能最优。先单独累计 p=100 的必胜游戏；若这部分奖金已超过上界，答案直接是它。否则对每个 p<100 只保留奖金最大的前若干个，因为再多取会让期望下降。之后做背包：dp[sum] 记录达到该奖金和的最大成功概率，枚举所有候选游戏更新，最大化 `sum*probability`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2252C": {
            "statement_brief": "二维积木塔有 n 层、每层 m 块。移除第 i 层一块会让第 i 层及以上稳定值减少该块伤害；塔因某层稳定值非正或某层被清空而倒塌，求最少移除块数。",
            "transformed_statement": "把题目先看成：答案一定不超过 m，因为清空任意一层即可倒塌；所以对每一层只需关心它及下方伤害最大的 m 块。",
            "key_observations": [
                "要通过伤害摧毁第 k 层，只能选第 k 层及以下的块。",
                "用最少块达到 v_k，显然应选这些可用块中伤害最大的若干块。",
                "由于答案至多 m，维护全局前 m 大伤害就够了。",
                "从底到顶扫描，逐层加入本层 m 个伤害，保留前 m 大并查前缀和是否达到该层稳定值。",
            ],
            "solution_brief": "关键观察：清空一层给了 `ans<=m` 的强上界。处理第 k 层时，候选块是所有行号 >=k 的块；只要维护其中最大的 m 个，就覆盖所有可能最优移除数。自底向上把本层块加入有序容器/堆，删掉第 m 大之后的元素，并用前缀和找最小件数使伤害和不少于 v_k，取全局最小。",
            "primary_topic": "数据结构",
        },
        "2237D": {
            "statement_brief": "二进制串可反复把相邻相同的两个字符删掉并替换成相反字符。统计多少非空子串能最终变成长度 1。",
            "transformed_statement": "把题目先看成：一个子串可化到长度 1，当且仅当 1 的数量减 0 的数量不被 3 整除，并且它不是长度大于 1 的交替串。",
            "key_observations": [
                "00->1 会让 f=#1-#0 增加 3，11->0 会让 f 减少 3，因此 f mod 3 不变。",
                "最终长度 1 的 f 为 1 或 -1，所以 f 不能为 0 mod 3。",
                "长度大于 1 的交替串没有相邻相同字符，无法操作。",
                "反过来，只要满足这两个条件，总能找到一对相同字符操作，并保持条件直到长度 1。",
            ],
            "solution_brief": "关键观察：先给可化简性一个精确判定。用前缀和模 3 统计所有 f 非零的子串数：当前位置贡献为此前不同模值前缀数量之和。然后减去其中长度大于 1 的交替子串；扫描维护当前交替后缀长度，就能把奇数长度且 f 非零的交替子串扣掉。",
            "primary_topic": "字符串",
        },
        "2232A": {
            "statement_brief": "n 个人在数轴上。一次群聊只能叫两个人，让他们移动到两人当前位置之间的某个整数点。求让所有人汇合的最少群聊次数。",
            "transformed_statement": "把题目先看成：若最终汇合点固定在 x，左边的人和右边的人可以一对一向 x 合并，次数由较多的一边决定。",
            "key_observations": [
                "一次群聊最多能同时推进一个在左侧的人和一个在右侧的人到目标点。",
                "若一侧人数更多，多出来的人还需要单独与已在目标点的人通话。",
                "因此固定 x 的代价是 max(左侧人数, 右侧人数)。",
                "最优 x 取中位数位置；排序后答案等价于不对称配对数量的一半。",
            ],
            "solution_brief": "关键观察：目标点取中位数最平衡。排序后，把最左和最右的人配对向中间汇合；已经在对应中位位置的人不需要额外代价。实现上可数有多少 i 满足 a_i 与镜像位置不同，答案为这个数量的一半。",
            "primary_topic": "构造与贪心",
        },
        "2231D": {
            "statement_brief": "已知数组 a 的部分元素以及其前缀和数组的前缀最大值 c，要求补全 a，使得到的前缀最大值恰好为 c，或判无解。",
            "transformed_statement": "把题目先看成：c 不变的一段里，前缀和必须一直不超过该段最大值；c 上升的位置则精确决定前一个前缀和。",
            "key_observations": [
                "c_i 不可能下降；若下降直接无解。",
                "当 c_i 与 c_{i+1} 不同，前缀和 b_i 必须等于 c_i，否则下一个最大值无法从 c_i 跳走。",
                "在 c 相等的一段，如果遇到未知 a，可以在段首填一个极小负数，让这一段内部前缀最大不会被破坏。",
                "构造后再整体模拟一次前缀和与前缀最大，作为最终合法性检查。",
            ],
            "solution_brief": "关键观察：前缀最大数组把若干位置的真实前缀和钉死。按 c 的变化切段，从右往左/按段恢复：若某个边界后 a_{i+1} 已知，就能反推出 b_i；若段内有未知位，就用一个足够小的负数压住后续前缀和，避免制造新最大。填完所有缺失值后重新计算前缀最大，等于给定 c 才输出。",
            "primary_topic": "构造与贪心",
        },
        "2229E": {
            "statement_brief": "给一棵树。重复 n-1 次：把当前编号最大的叶子加入集合 S，然后删除另一个叶子。问最终可能得到多少种不同集合 S。",
            "transformed_statement": "把题目先看成：以编号 n 为根；当某个点 x 第一次能成为最大叶子时，此前集合最大值必须夹在 x 和 x 子树内部最大编号之间。",
            "key_observations": [
                "编号 n 永远不会被删，且最终一定会进入 S，所以以 n 为根最自然。",
                "要让 x 成为叶子，必须先删空 x 的子树内部。",
                "如果当前最大叶子大于 x 子树内部最大编号，就能删完整个子树而不改变当前最大值。",
                "因此从状态 max(S)=i 能转移到 j，当且仅当 max(subtree(j))<i<j；这些转移是区间形式。",
            ],
            "solution_brief": "关键观察：集合 S 的演化只需记录当前最大值。预处理每个节点子树内最大编号，设 dp[i] 为达到 `max(S)=i` 的方案数。若节点 j 满足 `subMax[j]<i<j`，就能在不引入其它新最大值的情况下把 j 加入 S。用前缀和批量处理这些区间转移；转移到根 n 有特殊条件，需要能删掉根的其它儿子子树。",
            "primary_topic": "树结构",
        },
        "2228C2": {
            "statement_brief": "给非负整数 a 和一个可用数字集合 d，求只由 d 中数字组成的非负整数 b，使 |a-b| 最小。",
            "transformed_statement": "把题目先看成：分别求不小于 a 的最小合法数和不大于 a 的最大合法数，再取距离较小者。",
            "key_observations": [
                "若要找大于等于 a 的最小合法数，沿最长公共前缀扫描，首次必须变大的一位取比当前位大的最小可用数字，后面全填最小可用数字。",
                "若当前位置无法变大，就回退到更高位尝试增大；也要考虑位数比 a 多一位的情况。",
                "找小于等于 a 的最大合法数完全对称：首次变小的一位取比当前位小的最大可用数字，后面全填最大可用数字。",
                "需要单独处理 0 是否在可用数字集合内，避免把非法前导零数当答案。",
            ],
            "solution_brief": "关键观察：最近合法数一定在与 a 的最长公共前缀处分叉。写两个函数：`ceilLegal(a)` 构造最小的合法上界，`floorLegal(a)` 构造最大的合法下界；每个函数从高位扫，失败就向前回退调整一位，并把低位填成极小/极大数字。最后比较两个候选与 a 的差。",
            "primary_topic": "构造与贪心",
        },
        "2215E": {
            "statement_brief": "平面上有 n 个横纵坐标均互异的点，要连边形成若干内部不相交、且每个三角形都能落在某个轴平行矩形边界上的三角形；求最大数量并构造。",
            "transformed_statement": "把题目先看成：这是受限平面三角剖分。三角形数由外脸点数决定，目标是让必须在外脸上的点尽量少，并构造达到等号的剖分。",
            "key_observations": [
                "对平面图用欧拉公式，可得三角形数 t<=2(n-1)-x，其中 x 是外脸点数。",
                "若以某点为原点存在一个空象限，该点必须在外轮廓上。",
                "按 y 从小到大插入点，维护左、右两条 x 单调链。",
                "新点破坏某条单调链时，弹出的相邻两点和新点正好形成一个合法矩形边界三角形。",
            ],
            "solution_brief": "关键观察：先用欧拉公式把最大三角形数转成最小外脸点数，再用两条单调栈构造达到上界的剖分。按 y 排序插入点；左栈保持 x 递增，右栈保持 x 递减。若新点 x 更靠左，就不断弹左栈并输出“新点、弹出点、弹出后栈顶”的三角形；右侧对称。每个点入栈出栈常数次，构造出的三角形互不穿插且数量达到界。",
            "primary_topic": "几何",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2210D": {
            "statement_brief": "给两个合法括号序列。一次操作可交换两个不相交且本身也是合法括号序列的子串，问能否把 s 变成 t。",
            "transformed_statement": "把每个括号对看成树上节点，外面再套一层根；交换合法括号子串就变成交换某些连续儿子子树。",
            "key_observations": [
                "操作可逆，所以只要两棵括号树能化到同一个规范形即可。",
                "整棵树的叶子数量不变，因为操作只搬动完整子树。",
                "从根往下第一个拥有多个儿子的节点深度不变；它上方只有单链，无法被交换破坏。",
                "若这两个不变量相同，可以反复把更深分叉子树搬到该节点下，最终变成同一个“一个分叉点挂若干链”的规范形。",
            ],
            "solution_brief": "关键观察：不要在字符串上模拟交换，而是转成括号树找不变量。叶子数对应原串中相邻的 `()` 数量；最高分叉点深度可用外层连续包裹层数表示。分别计算 s 和 t 的这两个量，相同则可互相变换，否则不行。",
            "primary_topic": "树结构",
        },
        "2207B": {
            "statement_brief": "m 个危险值每秒有一个加一；若干固定时刻可以把一个危险值清零。对手选择加谁，你选择清谁，求能保证的最终最大危险值最小是多少。",
            "transformed_statement": "守卫的最优动作永远是清当前最大值；剩下只需分析对手怎样让被清掉的危险值总和尽量小。",
            "key_observations": [
                "清当前最大值同时逐项不劣于清任何其它值。",
                "若还剩 k 次清零，对手给前 k+1 大以外的值加一没有意义，它之后不可能成为决定性值。",
                "当剩余清零次数少于 m 后，每次被清零的对象会退出活跃竞争，最终危险只会累积到一个未清对象上。",
                "最终最大值等于总秒数减去被清零时刻那些危险值之和，因此对手要让这些被清值尽量小。",
            ],
            "solution_brief": "关键观察：先确定双方最优结构。守卫每次清最大；对手只在仍可能被清的活跃集合中加最小值，让未来清零收益最小。按题解可以直接模拟这个贪心过程，或者等价维护活跃危险值，最后答案是 `l - 清零收益和`。",
            "primary_topic": "博弈",
        },
        "2192A": {
            "statement_brief": "给一个字符串，可以任意循环旋转，分数是最终字符串的连续相同字符块数，求最大分数。",
            "transformed_statement": "旋转只会改变首尾拼接处；想让块数增加，只能把一个长度至少为 2 的块切到首尾两端。",
            "key_observations": [
                "除首尾连接处外，旋转不会改变相邻字符是否相同。",
                "块数最多只可能比原串多 1。",
                "若原串首尾相同，说明某个块已经被切开，换个旋转反而会把它合并，不能再多拿 1。",
                "若不存在相邻相同字符，也没有可切开的块，答案就是原块数。",
            ],
            "solution_brief": "关键观察：只看首尾和是否存在相邻相同。先数原串块数；如果首尾不同且串内存在一对相邻相同字符，就能旋转到这对内部切开，答案加 1；否则答案保持原块数。",
            "primary_topic": "字符串",
        },
        "2160C": {
            "statement_brief": "定义 f(x) 为 x 的二进制反转后去掉前导零得到的数。给 n，问是否存在正整数 x 满足 `x xor f(x)=n`。",
            "transformed_statement": "把 x 和反转后的 x 对齐成同样长度看，`x xor f(x)` 必须是二进制回文；但 n 可能需要在高位补若干个 0 才是这个长度。",
            "key_observations": [
                "第 i 位和倒数第 i 位的结果都来自同一对 x 的比特异或，因此结果必须对称。",
                "n 的高位补零数量必须等于它二进制末尾 0 的数量，否则补出来的整体无法回文。",
                "确定长度后，只需检查补零后的 n 是否为回文。",
                "若长度为奇数，中间位必须是 0，因为它等于某一位和自身异或。",
            ],
            "solution_brief": "关键观察：必要条件几乎也是充分条件。令 n 的二进制串去掉前导零后为 s，统计末尾连续 0 个数 z，在左侧补 z 个 0 得到目标串。若它不是回文则无解；若有中间位且中间位为 1 也无解；其它位置都能反推出某个 x。",
            "primary_topic": "字符串",
        },
        "2156C": {
            "statement_brief": "白板上有 n 个数，可删除至多 k 个数，也可把一个数 x 拆成三段并只保留最小和最大两段。求最终所有数 gcd 的最大值。",
            "transformed_statement": "固定目标 gcd g，问题变成判断有多少原数可以不用删除就变成 g 的倍数。",
            "key_observations": [
                "删除操作可以全部提前做；删除拆出来的数不如直接删除它的来源。",
                "若 x 已是 g 的倍数，它天然可保留。",
                "若 x>=4g，一次拆分成 `g, g+x%g, x-2g-x%g`，保留的两段都是 g 的倍数。",
                "若 x<4g 且不是 g 的倍数，题解用强归纳证明无论怎么拆都无法把保留部分全变成 g 的倍数。",
            ],
            "solution_brief": "关键观察：固定 g 后，好数只有四类：`x>=4g`、`x=g`、`x=2g`、`x=3g`。若这些数量至少为 `n-k`，就能删掉其它数并让 gcd 至少为 g。因为 `a_i<=n`，用频次数组和前缀和枚举 g，取最大的可行值。",
            "primary_topic": "数论与同余",
        },
        "2152H1": {
            "statement_brief": "给一棵带权树。要给点赋非负权，使任意非空红色连通染色的“点权和+割边权”最小值至少为 l，并最小化点权总和；回答少量询问。",
            "transformed_statement": "真正需要约束的红点集合不是所有子集，而是按边权从大到小合并时出现的强集合。",
            "key_observations": [
                "最优红点集合可假设连通；若不连通，删掉一个红连通块不会增加代价。",
                "红色内部边必须都比割边更重，否则可以沿较轻内部边切开并降低代价。",
                "这类强集合正好对应按边权降序 Kruskal 合并过程中出现的 DSU 组件，总数只有 O(n)。",
                "约束变成对每个强集合 S 要满足 `cut(S)+sum(x_i in S)>=l`，可以在强集合树上自底向上贪心补点权。",
            ],
            "solution_brief": "关键观察：先把指数级红点集合压成 Kruskal 重构树上的 O(n) 个强集合。预处理每个强集合的割边权；对一次询问 l，自底向上处理强集合，若当前子树已有点权和加割边权不足 l，就在该集合任意叶子补足差额。简单版 q 很小，逐询问 O(n) 可过。",
            "primary_topic": "树结构",
        },
        "2129F2": {
            "statement_brief": "交互题。隐藏一个排列，可询问一组位置或一组值的前若干大结果；总询问次数很少，且大询问只能用一次，要恢复整个排列。",
            "transformed_statement": "把每个元素被哪些询问命中记成集合签名；返回结果也给出对应签名。签名唯一就能直接定位，签名成对重复则得到一个无序二元组。",
            "key_observations": [
                "简单版思路是设计很多不同签名集合，让每个位置/值可被唯一识别。",
                "困难版容量不够让所有签名唯一，于是故意让大量元素两两共用同一签名，先恢复无序对。",
                "一次大询问从每个无序对中取一个代表；若返回了最大值，就能确定它所在那一对的方向，并连锁确定更多对。",
                "重复概率按几何分布估算，300 个返回结果足以高概率解开约 436 个无序对。",
            ],
            "solution_brief": "关键观察：不要把交互询问当普通搜索，而是提前设计签名编码。先用 29 次小询问构造所有大小小于 3 的签名，并让每个签名对应两个候选，得到大量无序位置对；再用一次大询问抽每对一个元素，利用返回的前 300 大值确定这些对的方向。剩余少量元素用剩下的小询问补齐。",
            "primary_topic": "交互",
        },
        "2129E": {
            "statement_brief": "给无向图，多次询问编号区间诱导子图中每个点的邻点编号异或值，要求这些值的第 k 小。",
            "transformed_statement": "区间左右端点移动时，加入/删除一个点只影响它的邻边相关值；核心是让莫队移动代价按度数均摊，而不是按点数均摊。",
            "key_observations": [
                "标准莫队会反复处理高度数点，复杂度可能爆掉。",
                "把每个点的移动成本定义为 `degree+1`，再按成本前缀和分块，可以用握手定理控制总移动代价。",
                "维护当前区间内每个点的 f 值时，加入或删除端点只需枚举它的邻边更新异或。",
                "第 k 小可用值域分块维护计数，修改 O(1)，查询按块扫描。",
            ],
            "solution_brief": "关键观察：这是带非均匀移动成本的莫队。先按 `cost_i=deg_i+1` 的前缀和给左端点分块，块内按右端点排序；移动端点时枚举相关邻边更新各点异或值，并同步维护值域计数。由于总成本是 `n+2m`，莫队复杂度按这个总成本开根号估算。",
            "primary_topic": "数据结构",
        },
        "2101C": {
            "statement_brief": "给上界数组 a，构造 b 且 `1<=b_i<=a_i`，最大化每个值首末出现位置距离之和。",
            "transformed_statement": "每个值只关心第一次和最后一次出现；把一段距离拆成跨过的每条相邻缝隙，问题变成每条缝隙最多能被多少值覆盖。",
            "key_observations": [
                "同一个值中间出现多少次不影响贡献，只需安排首尾两次。",
                "距离 j-i 等于它跨过的缝隙数量，所以可以逐缝隙计数。",
                "对前缀，能放下多少个不同起点可用贪心匹配：每个 a_i 匹配当前不超过它的最大未用值。",
                "后缀同理；第 i 条缝隙最多被 `min(左侧可开头数, 右侧可结尾数)` 个值跨过。",
            ],
            "solution_brief": "关键观察：把总距离转成“每条缝隙被多少首尾对覆盖”。从左到右贪心计算每个前缀最多能作为多少个不同值的首次出现，从右到左算后缀最多能作为多少个末次出现；答案就是所有缝隙上的两侧能力较小值之和。",
            "primary_topic": "构造与贪心",
        },
        "2059B": {
            "statement_brief": "把数组分成恰好 k 个非空连续段，取偶数编号段拼成 b 并在末尾补 0；代价是第一个 `b_i!=i` 的位置，求最小代价。",
            "transformed_statement": "若 k<n，答案最多为 2，因为可以调第二段的起点；只有 k=n 时分段被完全固定。",
            "key_observations": [
                "k=n 时每段长度只能为 1，直接检查偶数位置拼出的 b。",
                "k<n 时，只要能让第二段第一个数不是 1，答案立刻为 1。",
                "第二段起点可选范围是 `[2, n-k+2]`。",
                "如果这个范围全是 1，也可以让第二段取两个 1，于是 b 的第二位不是 2，答案为 2。",
            ],
            "solution_brief": "关键观察：最小代价只盯 b 的开头。特判 k=n；否则扫描所有可能的第二段起点，若某个位置不是 1 输出 1。若全是 1，由于还存在额外长度可分配，让第二段包含两个 1，b 开头为 `1,1`，所以输出 2。",
            "primary_topic": "构造与贪心",
        },
        "2049A": {
            "statement_brief": "一次操作可选一个非空子数组并用它的 MEX 替换，要求把整个数组变成全 0，求最少操作次数。",
            "transformed_statement": "删掉首尾已有的 0 后，只需看剩下的非零元素是否连续。",
            "key_observations": [
                "若一开始全是 0，答案为 0。",
                "若所有非零元素形成一个连续段，直接选这段，其 MEX 为 0，答案为 1。",
                "若非零元素被中间的 0 隔开，一次操作不可能成功，因为必须选覆盖所有非零的段，而这个段含 0，MEX 不为 0。",
                "两次一定够：先把整个数组变成一个非零数，再把这个单元素数组变成 0。",
            ],
            "solution_brief": "关键观察：答案只有 0、1、2。去掉首尾 0 后，如果数组空则 0；如果内部没有 0，说明非零段连续，答案 1；否则答案 2。这个判断比模拟 MEX 操作简单得多。",
            "primary_topic": "基础实现与模拟",
        },
        "2020B": {
            "statement_brief": "n 个灯泡初始全亮；对每个 i 翻转所有 i 的倍数。要求最终亮灯数恰好为 k，求最小 n。",
            "transformed_statement": "第 x 个灯会被翻转约数个数次；最终仍亮当且仅当 x 的约数个数为偶数，也就是 x 不是完全平方数。",
            "key_observations": [
                "每个灯的最终状态只取决于它自身编号，不取决于 n 的其它部分。",
                "非平方数约数成对出现，约数个数为偶数；平方数有一个自配对平方根，约数个数为奇数。",
                "所以前 n 个灯中亮着的数量是 `n-floor(sqrt(n))`。",
                "问题变成找最小 n 满足 `n-floor(sqrt(n))=k`。",
            ],
            "solution_brief": "关键观察：亮灯就是非完全平方数计数。可以二分最小 n，使 `n-floor(sqrt(n))>=k`；由于该函数递增，二分范围到 `2e18` 即可。题解还给出直接式 `floor(k+sqrt(k)+0.5)`，但二分更稳。",
            "primary_topic": "数论与同余",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2258D": {
            "statement_brief": "两列超长网格中若干区间为黑格，每行最多选一个黑格；同一列连续选中的段按长度给出极大的指数分数，要求最大总分并压缩输出。",
            "transformed_statement": "由于分数随连续段长度极快增大，问题核心是把可选黑格压成若干区间端点，再在端点之间决定哪些连续段能被完整覆盖。",
            "key_observations": [
                "若一个黑区间被另一个黑区间完全包含，被包含区间不会提供更优选择，可以删掉。",
                "真正影响答案的只有所有区间的左右端点，端点之间的连续空白长度只作为段长参与分数。",
                "删去无用区间后，两列结构可以看成若干区间链。",
                "定义 dp[i] 为覆盖到第 i 个关键端点前的最优分数，若存在区间覆盖 `[j,i)` 就可从 j 转移到 i。",
            ],
            "solution_brief": "关键观察：不要按 1e18 行扫描，只保留区间端点。先删除被包含的黑区间，离散化端点；然后做区间链 DP，转移含义是选出一段连续黑格并获得对应长度的巨大分数。因为只有两列，能覆盖某段的候选关系可以压到 O(n^2) 处理。",
            "primary_topic": "动态规划与状态设计",
        },
        "2237C": {
            "statement_brief": "一排数未排序时，可以选择相邻逆序对 `(x,y)` 变为 `(y,x+y)`。过程终会有序，要求最终最大值尽量小。",
            "transformed_statement": "把操作看成较小值向左穿过较大值，并给被穿过的堆加上自己；最优策略可以固定为总是处理最左逆序。",
            "key_observations": [
                "不相邻冲突的操作顺序可交换，不影响关键结果。",
                "三个连续下降值 `x>y>z` 中，先处理左逆序最终最大值不大于先处理右逆序。",
                "交换论证后，可假设最优过程总取最左逆序。",
                "扫描已处理前缀的当前最大值 m，加入 x：若 `m<=x` 则新最大为 x，否则 x 会穿过 m，新最大为 `m+x`。",
            ],
            "solution_brief": "关键观察：不用模拟整个冒泡过程，只维护前缀最小可达最大值。左到右扫描，设 m 是当前有序前缀最终最大堆；若下一个 x 不小于 m，直接接上并令 m=x；否则它必须向左穿过最大堆，使最大堆增加 x，令 m+=x。最终 m 就是答案。",
            "primary_topic": "构造与贪心",
        },
        "2231E": {
            "statement_brief": "给一棵树和目标大小 d，选择三点并取包含它们的最小连通子图，统计子图大小恰为 d 的三点组数量。",
            "transformed_statement": "三点生成的最小子树要么是一条路径，要么是三条链在某个分叉点汇合；按这个分叉点计数。",
            "key_observations": [
                "若生成子树是一条路径，先数距离为 d-1 的端点对，再任选路径内部第三点。",
                "非路径情形一定有唯一分叉点 v，三点分别落在 v 的三个不同方向。",
                "预处理 `down[v][k]` 和 `up[v][k]`，表示子树内/子树外距离 v 为 k 的点数。",
                "枚举分叉点和来自不同儿子方向的两点后，第三点可在子树内或父侧补足剩余距离；子树内情形会被三次计数。",
            ],
            "solution_brief": "关键观察：按三点 Steiner 子树形态拆。路径情形单独统计；否则枚举分叉点 v，用距离计数数组快速知道某个方向外还剩多少点可选。对子树内第三点的计数最后除以 3，父侧第三点不重复。总复杂度利用每对点只在 LCA 处处理，做到 O(n^2)。",
            "primary_topic": "树结构",
        },
        "2226E": {
            "statement_brief": "对数组每个前缀，允许每个数各自取模一次，求能得到的最大 MEX。",
            "transformed_statement": "要让 MEX 至少为 k，需要制造出 0..k-1；原本等于某个小值的元素可固定，其它值则作为供给者去匹配缺失的接收值。",
            "key_observations": [
                "前缀变长时答案不会下降，可以用双指针逐步尝试增加 MEX。",
                "若一个供给值 a 要通过取模产生 r，关键可行条件是存在选择使得 a 大于 2r。",
                "把缺失的值视为接收者，把未固定的数组元素视为供给者；从大接收者往小接收者看，每个后缀都要有足够大的供给者。",
                "在线维护 `#供给者>=2i+1 - #接收者>=i` 的最小值，非负就说明匹配可行。",
            ],
            "solution_brief": "关键观察：最大 MEX 的判定可以变成一组后缀匹配约束。扫描前缀时新增元素会改变供给者或固定值；尝试把答案从 k 提到 k+1 时会新增一个接收者或把某个值改为固定。所有变化都是区间加，线段树维护全局最小值，能在 O(log n) 内判断当前 k 是否可行。",
            "primary_topic": "数据结构",
        },
        "2190B1": {
            "statement_brief": "给合法括号序列 s，找一个非空合法括号子序列 t，使 t 字典序严格大于 s，并最大化 t 长度；不存在则输出 -1。",
            "transformed_statement": "字典序变大只能发生在某个 s 的 `)` 位置，用后面的 `(` 顶替它；这会删除中间若干右括号，并需要再删除同样数量的左括号保持平衡。",
            "key_observations": [
                "设第一次不同位置为 i，则必须有 `s_i=')'` 且 `t_i='('`。",
                "为了长度最大，应选择 i 后面最近的 `(` 作为替换字符。",
                "若这个 `(` 在 j，中间跳过了 `j-i` 个字符，之后还要删掉 `j-i` 个左括号来保持左右括号数量相等。",
                "只要后缀中有足够多左括号可删，得到的子序列仍是合法括号序列。",
            ],
            "solution_brief": "关键观察：枚举第一次变大的位置，而不是枚举子序列。预处理每个位置右侧最近的 `(` 和后缀左括号数量；对每个 `)` 位置 i，令 j 为最近 `(`，若 j 后还有至少 `j-i` 个 `(` 可删，则候选长度为 `n-2*(j-i)`，取最大。",
            "primary_topic": "字符串",
        },
        "2154A": {
            "statement_brief": "给二进制串和 k。你先保护若干位置，随后从左到右每个未保护的 1 若前 k-1 位没有 1 就会被改成 0。求最少保护数，使字符串保持不变。",
            "transformed_statement": "一个 1 只有在它左侧距离 k 内已经有某个保留下来的 1 时才安全；否则它必须被保护。",
            "key_observations": [
                "第一个 1 必须保护，因为它前面没有 1 能挡住操作。",
                "若两个连续 1 的距离至少为 k，后一个 1 在处理时会看到前 k-1 位全是 0，因此必须保护。",
                "保护这个 1 后，它又能作为之后一段距离内的屏障。",
                "若距离小于 k，前一个 1 会阻止当前 1 被改动，不需要额外保护。",
            ],
            "solution_brief": "关键观察：答案就是从左到右数“必须成为新屏障”的 1。维护上一个 1 的位置；遇到 1 且距离上一个 1 至少 k，就必须保护，答案加一。无论这个上一个 1 是否保护，只要它保持为 1，就能保护后面距离不足 k 的 1。",
            "primary_topic": "构造与贪心",
        },
        "2152A": {
            "statement_brief": "初始数组全 0。操作一是给全体元素加同一个正数，操作二是把任意一些元素清零。给目标正数组，求最少操作数。",
            "transformed_statement": "每次清零最多把当前还一起增长的一批元素分出一个新的目标值，因此答案只和目标数组中不同数的个数有关。",
            "key_observations": [
                "连续两次同类操作总能合并，所以最优操作会在加法和清零之间交替。",
                "目标数组没有 0，首尾操作都必须是加法。",
                "一次清零最多把最终不同值数量增加 1，因此 m 个不同目标值至少需要 `2m-1` 次操作。",
                "按目标值从大到小构造：每次加相邻差值，再把下一档目标值对应位置清零，最后加最小值，可达到下界。",
            ],
            "solution_brief": "关键观察：不必输出操作序列。设目标数组有 m 个不同值，任何方案至少需要 m 次加法和 m-1 次清零；按降序差分可以构造达到这个次数，所以直接输出 `2m-1`。",
            "primary_topic": "基础实现与模拟",
        },
        "2150G": {
            "statement_brief": "给 x、y、k 和基准二进制串 a，统计字典序大于 a、含 x 个 0 和 y 个 1、且存在一个切分使两边最长非降子序列长度都至少 k 的串数。",
            "transformed_statement": "二进制串的最长非降子序列可以转成格路触线问题；字典序限制则通过枚举与 a 的首个不同位置处理。",
            "key_observations": [
                "含 x 个 0、y 个 1 的串对应从 (0,0) 到 (x,y) 的格路。",
                "当 x、y 都小于 k 时，LNDS 至少 k 等价于路径触到某条斜线，可用反射法计数。",
                "若给定前缀，剩余部分的合法补全只取决于当前 0 的数量、当前 LNDS 和剩余 0/1 数量。",
                "枚举字典序第一次从 0 改成 1 的位置，再枚举哪一侧第一次达到 k，可把计数压到组合数求和。",
            ],
            "solution_brief": "关键观察：先解决“固定 0/1 个数且 LNDS 至少 k”的闭式计数，再把它作为子程序处理前缀和切分。扫描 a，枚举第一个变大的位置，维护前缀 0/1 数和当前 LNDS；对剩余长度调用题解中的 f/g 公式统计左右两段都达标的补全。困难版再利用组合数系数规律把求和优化。",
            "primary_topic": "组合计数与概率",
        },
        "2150D": {
            "statement_brief": "n 个人初始在 1..n。每次在某点放吸引物，左边的人右移、右边的人左移、该点不动。统计所有可达最终位置数组的总得分。",
            "transformed_statement": "与其跟踪每个人，不如统计最终每个坐标的人数 f_i；可达 f 的非零位置必须形成一个连续区间，且内部人数全为奇数。",
            "key_observations": [
                "一次吸引操作本质上把相邻三个位置的人群向中间合并，边界位置特殊。",
                "可达最终分布的支撑集一定是连续区间 `[L,R]`。",
                "区间内部每个 f_i 必须为奇数；两端奇偶可以单独分类。",
                "固定区间长度和端点奇偶后，剩余人数分配成若干非负变量，变量对称，可用隔板法和期望贡献求总分。",
            ],
            "solution_brief": "关键观察：先刻画可达分布，再按区间求和。枚举支撑区间长度，分类两端奇偶，把内部写成 `2g_i+1`、端点写成 `2g_i+x/y`；方案数是隔板组合数，所有 g_i 对称，所以每个位置的平均贡献相同。用前缀和及前缀和的前缀和快速累加所有区间贡献。",
            "primary_topic": "组合计数与概率",
        },
        "2135E2": {
            "statement_brief": "二进制串反复同步删除所有 `10`，若原串和反串最终结果相同则称为近回文。给 n，统计长度为 n 的近回文串数量。",
            "transformed_statement": "把 0 记为 +1、1 记为 -1，令 b 为前缀和；近回文条件等价于 `min(b)+max(b)=b_n`。",
            "key_observations": [
                "删除 `10` 的过程可用前缀和最低点和最高点刻画，反串条件最终化成 min/max 与总和的等式。",
                "固定前缀和最小值 l 和最大值 r 后，计数变成从 (0,0) 到某点且不碰两条斜线边界的格路数。",
                "禁触两条斜线可用反射容斥得到组合数求和。",
                "困难版按宽度 `r-l` 聚合，利用组合数下标连续移动来压缩求和。",
            ],
            "solution_brief": "关键观察：先从字符串操作跳到前缀和几何。近回文等价于前缀和区间关于终点对称；固定 min/max 后，用两条边界的格路反射容斥计数“恰好触到两边界”的路径。再按 `max-min` 分组，预处理组合数前缀和，把原本枚举 l,r 的计数降下来。",
            "primary_topic": "组合计数与概率",
        },
        "2115B": {
            "statement_brief": "已知最终数组 b 和 q 次操作 `c_z=min(c_x,c_y)`，要求构造一个初始数组 a，使执行所有操作后恰好得到 b，或判无解。",
            "transformed_statement": "倒着看操作，维护每个位置在操作前必须至少达到的下界；最后取这些下界作为最小候选 a，再正向验证。",
            "key_observations": [
                "先放宽目标为最终 `c_i>=b_i`，倒推可得到初始数组必须满足的一组下界 l。",
                "倒序经过操作 `z=min(x,y)` 时，操作前的 z 会被覆盖，所以 z 自身旧值没有限制。",
                "为了让操作后 z 至少为 l_z，操作前 x 和 y 都必须至少为 l_z。",
                "取最小候选 a=l 后正向模拟；若结果正好等于 b，则可行，否则不存在。",
            ],
            "solution_brief": "关键观察：min 操作适合倒推下界。初始化 l=b，倒序处理每次操作：把 `l_z` 传播到 `l_x` 和 `l_y` 上取 max，然后清掉旧的 `l_z`。得到 a 后正向执行所有操作，最后逐位比较 b；不相等就输出 -1。",
            "primary_topic": "构造与贪心",
        },
        "2113C": {
            "statement_brief": "网格中有空地、石头和金矿。可在空地引爆，爆炸方框边界上的金会收集，严格内部的金会消失。求最多能收集多少金。",
            "transformed_statement": "只需要选择第一次爆炸的位置，使第一次损失的内部金矿最少；其余未损失金矿之后都能保证被收集。",
            "key_observations": [
                "第一次爆炸方框严格内部的金矿一定损失，边界金矿会被收集。",
                "第一次爆炸后，剩余金矿可以通过从中心向外一圈圈选爆炸点，最终全部收集。",
                "因此最大收集量等于总金矿数减去第一次爆炸内部损失的最小值。",
                "枚举所有空地作为第一次爆炸中心，用二维前缀和快速求它内部方框金矿数。",
            ],
            "solution_brief": "关键观察：后续操作不再需要优化，只优化第一次损失。统计总金矿数；对每个空格，计算以它为中心、半径 k-1 的内部方框中有多少金会消失，取最小损失。答案为总金矿数减最小损失，方框越界时按网格边界裁剪即可。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2110C": {
            "statement_brief": "有一段飞行高度差数组 d，其中部分未知；高度每步只能不变或加一，并且第 i 步高度必须落在区间 `[l_i,r_i]`。要求补全 d 或判无解。",
            "transformed_statement": "正向不急着定每个未知位，只维护当前高度可能落入的闭区间；最后再反向构造具体取值。",
            "key_observations": [
                "若 d_i 未知，则下一高度区间最多从 `[L,R]` 扩成 `[L,R+1]`。",
                "若 d_i 固定为 0 或 1，则整体平移对应高度差。",
                "每一步再与障碍允许区间 `[l_i,r_i]` 求交；交集空就无解。",
                "正向只保存可行高度范围，反向从任意最终高度往前选能落回上一范围的 d_i。",
            ],
            "solution_brief": "关键观察：未知高度差不需要立刻贪心选 0/1。正向维护第 i 个障碍后的所有可行高度范围，并记录每步范围；若某步交集为空输出 -1。反向从最后范围取一个高度，遇到未知 d_i 时优先选能回到上一范围的 0，否则选 1，最终得到一组合法程序。",
            "primary_topic": "构造与贪心",
        },
        "2107D": {
            "statement_brief": "树上每个点有一个苹果。每次选择当前仍有苹果的一条路径，写下 `(路径点数,u,v)` 并删除路径上的苹果。要求最终写出的序列字典序最大。",
            "transformed_statement": "每次应在当前森林中选择字典序最大的直径路径；删除所有这类路径后再统一按三元组降序输出。",
            "key_observations": [
                "为了让序列字典序最大，优先最大化本次删除路径长度，再按端点编号打破平局。",
                "树中任意两条直径必有公共点或公共边，因此删掉一条直径后，剩余各连通块的直径严格变短。",
                "沿着某个连通块的祖先链看，直径长度严格递增且总删除点数不超过 n，所以每个点参与的层数只有 O(sqrt n)。",
                "一个连通块的最优直径可用两次最远点搜索，并按端点编号做字典序 tie-break。",
            ],
            "solution_brief": "关键观察：局部反复取当前森林的最大直径是可行的，因为删直径会让子问题直径严格下降。维护待处理连通块；对每块求字典序最大直径三元组，删除路径并把剩余子树加入集合。收集所有三元组后按降序输出，复杂度由直径严格下降性质控制在 O(n sqrt n)。",
            "primary_topic": "树结构",
        },
        "2071D2": {
            "statement_brief": "给二进制无限序列前 n 项，之后 `a_m` 等于前 `floor(m/2)` 项异或和。多次给区间 `[l,r]`，求该区间元素和。",
            "transformed_statement": "单点递归可以扩展成前缀和递归：分别维护不超过 m 的偶数位和奇数位中 1 的数量。",
            "key_observations": [
                "先把 n 调成奇数并预处理到 2n，后面的结构按成对下标重复出现。",
                "对大于 2n 的位置，`a_m` 只和总前缀异或 p 以及 `a_floor(m/2)` 的奇偶层有关。",
                "在一段成对位置里，偶数下标和奇数下标贡献相同，都能由 `sum(floor(m/2))` 推出。",
                "因此求前缀和时每次把 m 规整到适合的模 4 形态，再递归到 `m/2`。",
            ],
            "solution_brief": "关键观察：不要逐项算 `[l,r]`，写函数 `prefix(m)` 返回前 m 项 1 的数量。预处理 `m<=2n` 的普通前缀和、偶位前缀和；若 m 更大，把末尾少数项调整掉，使剩余部分能按二元组折半表达，再递归计算 `prefix(m/2)`。答案为 `prefix(r)-prefix(l-1)`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2064D": {
            "statement_brief": "一只新权值 x 从右端开始向左吞并不大于自己的相邻权值，每吞一次自身变为异或。每个询问给 x，求能吞几个。",
            "transformed_statement": "按最高位分段跳。最高位小于当前 x 的数一定能被吞；最高位相同的数被吞后才可能让 x 的最高位下降。",
            "key_observations": [
                "若左边下一个数不能被吞，它的最高位一定不小于当前 x 的最高位。",
                "最高位严格小于 x 的一整段都必然可吞，吞完后的 x 可用区间异或一次更新。",
                "吞掉最高位相同的数后，x 的最高位会下降；这种关键吞并最多发生 O(log W) 次。",
                "预处理每个位置左侧最近的、最高位至少为 j 的位置，就能快速跳到下一次可能卡住的位置。",
            ],
            "solution_brief": "关键观察：模拟时不要一个个吞。对每个询问，从右往左反复跳过所有最高位更小的一段，用前缀异或更新 x；再检查最近的最高位足够大的数，若它大于 x 就停止，否则吞掉它并让最高位下降。每次下降一位，所以每个询问 O(log W)。",
            "primary_topic": "数据结构",
        },
        "2062E1": {
            "statement_brief": "树上删子树游戏。首手先任选一个点删除其子树，之后每次只能选权值更大的剩余点并删其子树；不能操作的人获胜。要求找一个首手必赢点。",
            "transformed_statement": "首手要选一个点 u，使得 u 子树外存在权值更大的点；在所有满足条件的点里选权值最大的即可。",
            "key_observations": [
                "若 u 子树外没有更大权值点，对手无路可走，按题意反而是首手输。",
                "若 u 子树外存在更大权值点，首手至少能把回合交给对手。",
                "选择满足条件且权值最大的 u 后，对手之后只能选不满足该条件的点，首手会在下一轮无操作而获胜。",
                "判断子树外是否有更大权值，可用 DFS 序把子树变成区间，再查区间外最大值。",
            ],
            "solution_brief": "关键观察：胜负判定在第一步就能压成“子树外有无更大权值”。DFS 得到 `dfn/low`，预处理 DFS 序上的前缀最大和后缀最大；对每个点 u，若区间外最大值大于 w_u，则它是候选。输出候选中权值最大的点即可。",
            "primary_topic": "树结构",
        },
        "2055B": {
            "statement_brief": "有 n 类材料。一次操作选一类加 1，其它所有类各减 1。给当前量 a 和需求 b，问能否通过若干操作让所有类都达到需求。",
            "transformed_statement": "最优方案不会同时补两种不同短缺材料；否则两次操作叠加只会白白消耗其它材料。",
            "key_observations": [
                "若对两种材料都使用补充操作，它们自身净变化相互抵消，其它材料却都减少，必然不优。",
                "因此最多只能有一类材料初始不足。",
                "若没有不足，直接可行。",
                "若只有材料 i 不足 x，则其它每类材料都必须至少有 x 的富余来支付这 x 次操作。",
            ],
            "solution_brief": "关键观察：先数不足项。若不足项超过一个，输出 NO；若没有不足，输出 YES；若唯一不足为 i，令缺口 `need=b_i-a_i`，检查所有 `j!=i` 是否满足 `a_j-b_j>=need`。全部满足才可行。",
            "primary_topic": "构造与贪心",
        },
        "2053I1": {
            "statement_brief": "给数组 a，要求扩展成数组 b，使 a 是 b 的子序列、总和不变，并先最小化 b 的最大子数组和，再在此基础上最小化 b 长度。",
            "transformed_statement": "最小可能最大子数组和等于总和 p；于是问题变成在插入额外数后，让所有前缀和始终留在 `[0,p]`，并最少插入。",
            "key_observations": [
                "若某个前缀和小于 0 或大于 p，就能选出和大于 p 的子数组，违反最小 boredom。",
                "反过来，所有前缀和都在 `[0,p]` 时，任意子数组和都不超过 p。",
                "朴素 DP 维护处理到第 i 个原数组元素后可能的前缀和及最少插入数。",
                "最优 DP 值所在的前缀和集合始终是一段连续区间，因此只需维护区间 `[l,r]` 和当前最小插入数 v。",
            ],
            "solution_brief": "关键观察：把最大子数组和转成前缀和区间约束。顺序加入 a_i：若平移后的最优前缀和区间仍与 `[0,p]` 有交，就直接更新区间；否则必须插入一个额外数把前缀和拉回合法区间，插入数加一并重置可达区间。最后根据终点是否已能到 p 再补一次，得到最小长度。",
            "primary_topic": "动态规划与状态设计",
        },
        "2030G1": {
            "statement_brief": "给 n 个区间。一次扩展可把某个区间左端减一或右端加一；一个非空集合的分数是让集合内所有区间有公共交点所需的最少扩展次数。求所有非空集合分数之和。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：每个集合的代价等价于把这些区间扩到有公共交点的最小总扩展量。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
        "2022E1": {
            "statement_brief": "部分格子已填 0 到 `2^30-1` 的数。要求补全矩阵，使任意子矩形四角异或为 0，求补全方案数。",
            "transformed_statement": "美丽矩阵等价于存在两个数组 X、Y，使每个格子满足 `A[i][j]=X[i] xor Y[j]`；已知格子就是行点和列点之间的异或边约束。",
            "key_observations": [
                "任意四角异或为 0 会推出所有格子都能拆成行势能和列势能的异或。",
                "把 n 个行和 m 个列看成二分图点，已知格 `(i,j)=w` 是边约束 `X_i xor Y_j=w`。",
                "若图中某个环的边权异或不为 0，则约束矛盾，答案为 0。",
                "若无矛盾，每个连通分量有一个自由的 30 位整体异或量，方案数为 `(2^30)^(组件数-1)`。",
            ],
            "solution_brief": "关键观察：矩阵约束转成带异或权的二分图势能。DFS 每个连通分量，维护从根到点的异或值；遇到已访问边时检查两端势能异或是否等于边权。若矛盾输出 0；否则统计连通分量数 K，答案为 `2^(30*(K-1))`。",
            "primary_topic": "图论与网络流",
        },
        "2020C": {
            "statement_brief": "给 b、c、d，要求找非负 a，使 `(a|b)-(a&c)=d`，无解输出 -1。",
            "transformed_statement": "这个式子可逐二进制位独立判断，因为 `(a|b)` 的某位不可能小于 `(a&c)` 的同位，不会产生向高位借位。",
            "key_observations": [
                "对每一位，只需要枚举或推导这一位的 a、b、c、d 关系。",
                "不存在借位，所以低位选择不会影响高位。",
                "当 `(b,c,d)` 位为 `(1,0,0)` 时，无论 a 是 0 还是 1，该位结果都不可能为 0。",
                "当 `(b,c,d)` 位为 `(0,1,1)` 时同样不可能；其它情况可以直接确定 a 的该位。",
            ],
            "solution_brief": "关键观察：按位构造 a。遍历 0..61 位，读出 b、c、d 当前位；遇到两种非法三元组就输出 -1。否则若 b 和 c 都为 1，则 a 位取 `1-d_bit`；其它情况 a 位取 `d_bit`。最后输出构造出的 a。",
            "primary_topic": "基础实现与模拟",
        },
        "2255F": {
            "statement_brief": "把 n 个带标签数按环排列，权值为每条相邻边两端数之和的乘积；旋转视为相同、翻转不同，求所有环排列权值和。",
            "transformed_statement": "展开每条边的 `(a_u+a_v)`，等价于给环上每条边定向并选择被指向端点；每个变量指数只会是 0、1、2。",
            "key_observations": [
                "指数为 0 和指数为 2 的顶点数量必相等，去掉指数为 1 的普通点后，两类特殊点必须在环上交替。",
                "固定有 k 个二次点和 k 个零次点时，该单项式类型在所有环排列中的系数只依赖 k。",
                "答案可写成初等对称多项式组合 `sum h_r e_r e_{n-r}`。",
                "系数比较得到上三角线性方程；利用相邻系数比值和 Pascal 恒等式可化成二阶递推。",
            ],
            "solution_brief": "关键观察：先把环排列求和转成对称多项式系数问题。用分治 NTT 求 `prod(1+a_i x)` 的所有 `e_r`；再根据题解推导的递推求出 `h_r`，最终累加 `h_r*e_r*e_{n-r}`。难点不在环枚举，而在把每种指数模式的组合系数压成只依赖 k。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2252E": {
            "statement_brief": "统计 `1<=a<b<c<=n` 且成等差数列、同时 `a xor b xor c=0` 的三元组数量。",
            "transformed_statement": "由等差得到 `2b=a+c`，由异或得到 `b=a xor c`，于是只需数满足 `a xor c = 2*(a&c)` 的有序端点对。",
            "key_observations": [
                "利用恒等式 `a+c=(a xor c)+2*(a&c)`。",
                "把 `b=a xor c` 代入 `2b=a+c` 后，条件化为 `a xor c = 2*(a&c)`。",
                "每个合法 `(a,c)` 唯一确定 b，且原条件会保证 b 位于 a 和 c 之间。",
                "这个等式表示当前位的 `a&c` 必须等于上一高位的 `a xor c`，适合从高位到低位数位 DP。",
            ],
            "solution_brief": "关键观察：把三元组计数降成二元位约束。数位 DP 同时维护 c 是否仍贴着 n、a 是否已经严格小于 c、以及当前位所需的 `a&c` 值；枚举 a 和 c 的当前位，下一位的需求就是当前位 `a xor c`。处理完所有位后要求需求为 0 且 `a<c`。",
            "primary_topic": "动态规划与状态设计",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2234A": {
            "statement_brief": "给一个多重集合 b，问能否重排成某两个正整数 x>=y 的欧几里得算法序列：前两项为 x,y，之后每项等于前两项取模。",
            "transformed_statement": "欧几里得序列必然非增，因此若存在可行重排，唯一候选就是把 b 从大到小排序。",
            "key_observations": [
                "`a_2<=a_1`，且从第三项开始 `a_{i+1}=a_{i-1} mod a_i<=a_i`，所以整个序列非增。",
                "排序后的顺序是唯一可能顺序，不需要枚举排列。",
                "长度为 2 时只需输出排序后的前两项；长度更大时逐项检查取模关系。",
                "一旦某个 `a_{i+2} != a_i mod a_{i+1}`，任何其它重排也不可能合法。",
            ],
            "solution_brief": "关键观察：先用单调性杀掉排列搜索。把 b 降序排序为 a，检查所有连续三项是否满足欧几里得递推；全部满足就输出 `a_1,a_2`，否则输出 -1。",
            "primary_topic": "数论与同余",
        },
        "2222A": {
            "statement_brief": "OI 赛有 n 题，每题满分 100，第 i 题分成 `a_i` 个等分子任务，`a_i` 都整除 100。问是否能凑出 0 到 `100n` 的每个整数总分。",
            "transformed_statement": "要能得到总分 1，必须存在一题每个子任务正好 1 分，也就是某个 `a_i=100`；这个条件同时也是充分的。",
            "key_observations": [
                "每题分数增量是 `100/a_i`，若没有 `a_i=100`，所有非零增量都大于 1，不可能凑出总分 1。",
                "若有一题 `a_d=100`，它可以提供任意 0..100 的余数分。",
                "对于超过 100 的目标分数，先让若干其它题拿满分贡献整百，再用这道 100 子任务题补余数。",
                "因此只需判断数组里是否出现 100。",
            ],
            "solution_brief": "关键观察：题目看似是有界背包，实际上被目标分数 1 卡死。扫描所有 `a_i`，存在 100 输出 YES，否则输出 NO。",
            "primary_topic": "数论与同余",
        },
        "2202B": {
            "statement_brief": "初始串 T 是 `abab...`，每次删 T 的首字符或尾字符并追加到 S。给含 `?` 的 X，问能否补成某个可生成的 S。",
            "transformed_statement": "首尾删法生成的串只受相邻分组约束；`?` 不需要构造，只要检查固定字符是否违反这些约束。",
            "key_observations": [
                "当剩余 T 的两种交替形态长度相同时，它们通过左右操作互相镜像，后续等价。",
                "若 n 为奇数，第一步只能取到字符 a，所以 `S_1` 必须能是 a。",
                "之后按长度奇偶分组：n 为奇数时检查 `S_{2i}` 与 `S_{2i+1}` 不同；n 为偶数时检查 `S_{2i-1}` 与 `S_{2i}` 不同。",
                "带 `?` 的位置可以自由补，只要一对已知字符没有被迫相等即可。",
            ],
            "solution_brief": "关键观察：不用模拟双端队列，生成串等价于若干二元组必须一 a 一 b。先处理 n 奇数时首字符约束，再按对应二元组扫描；若某组两边都是已知且相同则 NO，否则 YES。",
            "primary_topic": "字符串",
        },
        "2196B": {
            "statement_brief": "给数组 a，计数满足 `a_i*a_j = j-i` 的下标对 `(i,j)`。",
            "transformed_statement": "合法对的距离被两个值的乘积决定；若两个值都很大，乘积会超过最大距离，所以至少一端必须是小值。",
            "key_observations": [
                "取阈值 `B≈sqrt(n)` 后，不可能出现 `a_i>=B` 且 `a_j>=B` 的合法对，因为乘积至少 n 而距离最多 n-1。",
                "当 `a_i` 较大时，以步长 `a_i` 枚举候选 j，数量最多 `n/B`。",
                "当 `a_i` 较小时，只需枚举有限个倍数 k；其它情况会在另一端枚举时被覆盖。",
                "三种大小组合覆盖所有合法对，且不会漏掉一端小一端大的情况。",
            ],
            "solution_brief": "关键观察：把等式改成“候选下标必须落在 `i + k*a_i` 上”，再用根号阈值控制枚举量。对大值按步长枚举两侧候选；对小值只枚举前向少量 k，并检查等式。因为双大不可能合法，总复杂度 `O(n sqrt n)`。",
            "primary_topic": "构造与贪心",
        },
        "2194E": {
            "statement_brief": "n*m 网格有权值，先手会选一条从左上到右下、只向右或下的最大权路径。后手先把一个格子权值取反，想最小化先手最终可得最大路径权。",
            "transformed_statement": "后手若不动原最大路径上的格子，先手仍可走原路径；所以只需考虑取反某条原最大路径 S 上的格子。",
            "key_observations": [
                "固定原最大路径 S，取反 S 上格子 c 后，先手可以继续走 S，收益变为 `maxS-2*a_c`。",
                "先手也可以改走一条绕开 c 的路径；这类路径必须在 c 的左上/右下相对区域中找到一个绕行点。",
                "用 `dpS` 表示从起点到每格的最大路径和，`dpT` 表示从每格到终点的最大路径和。",
                "绕行点贡献为 `dpS[x][y]+dpT[x][y]-a[x][y]`，按行列前缀最大值预处理后，每个 S 上格子的最好绕行值可 O(1) 得到。",
            ],
            "solution_brief": "关键观察：后手目标不是任意格子，而是某条最大路径上的瓶颈格。先求一条最大路径 S 和 `maxS`，再对 S 上每个格子计算两种先手反制：继续走 S、或绕开该格。该格被取反后的结果是二者最大值，后手取这些值的最小者。",
            "primary_topic": "动态规划与状态设计",
        },
        "2192B": {
            "statement_brief": "给二进制串 s。一次操作选择一个下标 i，并翻转除 i 以外的所有位；每个下标最多选一次。要求把串变成全 0，输出任意操作或 -1。",
            "transformed_statement": "只关心每一位最终被翻转次数的奇偶。若操作集合大小为 x，被选中的位翻转 `x-1` 次，没被选中的位翻转 x 次。",
            "key_observations": [
                "0 位最终必须被翻转偶数次，1 位最终必须被翻转奇数次。",
                "若 0 的个数为奇数，选择所有 0 位：0 位翻转偶数次，1 位翻转奇数次。",
                "若 0 和 1 的个数都为偶数，选择所有 1 位同样可行。",
                "唯一无解是 n 为奇数且 1 的个数为奇数，此时 0 的个数为偶数，无法满足两类奇偶。",
            ],
            "solution_brief": "关键观察：构造操作集合即可。若 `n` 和 1 的个数都为奇数，输出 -1；否则若 0 的个数为奇数就输出所有 0 的位置，否则输出所有 1 的位置。",
            "primary_topic": "构造与贪心",
        },
        "2183F": {
            "statement_brief": "树上每个点有字符。对每个 i，考虑从 i 子树内任选起点并不断跳到当前点的真子树中形成的所有字符串，求各字符串出现次数平方和。",
            "transformed_statement": "次数平方和等于选择两条生成路径且字符串完全相同的有序对数量；于是可以做两条路径同步的 DP。",
            "key_observations": [
                "令 `f[i][j]` 表示从 i、j 两个当前点出发，后续生成相同字符串的路径对数量；若字符不同则为 0。",
                "若字符相同，下一对点 `(p,q)` 只要求 p 在 i 的子树中、q 在 j 的子树中。",
                "DFS 序把每个子树变成连续区间，所以所有可转移的 `(p,q)` 在二维平面上是一个矩形。",
                "按 DFS 序逆序处理，并维护二维后缀和，就能快速求每个矩形内的转移总和。",
            ],
            "solution_brief": "关键观察：把“相同字符串计数”换成“两条路径配对计数”。先求 DFS 序；按逆序枚举点对 `(i,j)`，字符相同才计算 `f[i][j]`，其转移来自两个子树区间构成的矩形，用二维后缀和查询。每个询问根 i 的答案再由其子树内起点对汇总得到。",
            "primary_topic": "树结构",
        },
        "2174C1": {
            "statement_brief": "长度 n 的随机颜色串，每个位置独立均匀从 m 种颜色中选。定义 correctness 为非空回文子段数量，beauty 为 correctness 的平方，求 beauty 的期望模质数 p。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：目标是计算所有回文子段计数平方的期望，也就是回文子段有序对同时成立的概率和。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
        "2166A": {
            "statement_brief": "给小写字符串 s。一次操作可选 `i<n`，把 `s_i` 改成当前 `s_{i+1}`。问最少多少次能让所有字符相同。",
            "transformed_statement": "最后一个字符永远不会被修改，所以最终整串只能变成原来的 `s_n`。",
            "key_observations": [
                "操作只会把左边字符改成右边字符，无法改变 `s_n`。",
                "因此所有不等于 `s_n` 的位置都至少要被操作一次。",
                "从右往左处理时，若 `s_i != s_n`，操作 i 后它会变成已经修好的右侧字符 `s_n`。",
                "等于 `s_n` 的位置不需要操作。",
            ],
            "solution_brief": "关键观察：目标字符被最后一位锁死。答案就是前 `n-1` 个位置中不等于 `s_n` 的字符数量；从右到左逐个改可以达到这个下界。",
            "primary_topic": "字符串",
        },
        "2158F2": {
            "statement_brief": "构造长度 n 的正整数序列，要求所有相邻 gcd 两两不同，并且使用的不同数个数尽量少；困难版 `n<=5000`。",
            "transformed_statement": "把不同取值看成完全图点，序列相邻位置就是在图上走一条边；相邻 gcd 不同等价于经过的边标签互不相同。",
            "key_observations": [
                "若选出 k 个不同数 X，且所有无序点对和自环的 gcd 标签都不同，则问题变成在带自环完全图中找尽量长的不重复边游走。",
                "k 为奇数时可以走遍所有 `k(k+1)/2` 条边；k 为偶数时需要删去一个匹配来修正奇度点，最大长度为 `k^2/2+1`。",
                "因此最少不同数个数由上述最大可构造长度是否达到 n 决定。",
                "困难版用二维指数构造 `x_{i+jM}`，让任意两点 gcd 的质因子指数向量唯一，从而保证边标签不同且数值不超过 `1e18`。",
            ],
            "solution_brief": "关键观察：先构造“边标签全不同”的点集，再用欧拉游走输出序列。取最小 k 使图上可走边数至少 n；生成 k 个特殊数作为点，若 k 偶数先删一个匹配修正奇偶，再求欧拉路径/回路，按访问点顺序输出对应整数即可。",
            "primary_topic": "图论与网络流",
        },
        "2158D": {
            "statement_brief": "给两个等长二进制串 s、t。一次可选择当前 s 中一个长度至少 2 的回文子串并翻转其中所有位，要求用不超过 `2n` 次把 s 变成 t。",
            "transformed_statement": "只要证明任意二进制串能在 n 次内变成全 0，就可以把 s 先归零，再反向执行 t 归零的操作得到 t。",
            "key_observations": [
                "若串是交替的，`s[2..4]` 必为 010 或 101，翻转后能制造一段相邻相等字符。",
                "一旦存在相邻相等块 `[L,R]`，这段本身是回文且全相同。",
                "若右侧相邻字符不同，翻转 `[L,R]` 后块内仍全相同，并且右边界会与 `R+1` 相同，从而扩张一位；左侧同理。",
                "每次操作都能把相等块扩大一位，最终全串变常数；若是全 1，再翻转整串。",
            ],
            "solution_brief": "关键观察：构造的是“扩张同色块”，不是搜索回文。写一个函数把任意串变成 0：必要时先用 `[2,4]` 打破交替，然后找到相邻相等块，向左右扩张并记录操作，最后若全 1 翻转全串。答案为 `s->0` 的操作加上 `t->0` 操作的逆序。",
            "primary_topic": "字符串",
        },
        "2152G": {
            "statement_brief": "根树上一些点有怪物。每次询问翻转某个子树内所有点的怪物状态，询问后求最少多少条从根出发的路径能覆盖所有怪物点。",
            "transformed_statement": "最少路径数等于怪物点最大祖先无关集合大小；再把这个树上反链问题转成欧拉序上的最长交替子序列。",
            "key_observations": [
                "任意祖先无关的怪物集合需要不同路径终点覆盖，给出下界；最优路径的终点也可缩到怪物点，且这些终点互不为祖先，给出上界。",
                "DFS 欧拉序中，每个空点进入/退出记为 0/1；怪物点进入/退出记为 2/3。",
                "最大怪物反链大小等于欧拉序中最长 `2,3,2,3,...` 交替子序列长度的一半。",
                "翻转一个子树等价于把欧拉序对应区间内所有值异或 2，即 0/1 与 2/3 互换。",
            ],
            "solution_brief": "关键观察：路径覆盖数先变成最大反链，再变成序列维护。建欧拉序线段树，每个节点维护从 0/1/2/3 开始的若干最长交替子序列长度；区间翻转打懒标记异或 2。每次询问后根节点中 `2,3` 交替长度除以 2 就是答案。",
            "primary_topic": "数据结构",
        },
        "2138A": {
            "statement_brief": "两人最初各有 `2^k` 块蛋糕，总数固定为 `2^(k+1)`。每步一方把自己当前蛋糕数的一半给对方，要求最少步数达到 Chocola 恰好有 x 块并输出操作序列。",
            "transformed_statement": "正向操作不好选，但从目标状态往回看，若某一方少于一半，则上一手必然是这一方把一半给了对方。",
            "key_observations": [
                "操作 1 后 Vanilla 至少拥有总数的一半；操作 2 后 Chocola 至少拥有总数的一半。",
                "因此若当前 `0<a<2^k`，上一手只能是操作 1；若当前 `0<b<2^k`，上一手只能是操作 2。",
                "从 `(x,2^(k+1)-x)` 倒推到 `(2^k,2^k)` 的每一步都是唯一的。",
                "两人的蛋糕数在倒推中共同少一个 2 因子，所以最多只需要 k 步。",
            ],
            "solution_brief": "关键观察：最短序列直接倒推出来。维护当前 `(a,b)`；若 a 小于半数，就逆操作 1，把 a 翻倍、b 减去 a，并记录正向操作 1；若 b 小于半数则同理记录操作 2。到初态后把记录反转输出。",
            "primary_topic": "构造与贪心",
        },
        "2128F": {
            "statement_brief": "无向连通图每条边权可在 `[l_i,r_i]` 内任选，给定点 k，问能否赋权使 `dist(1,n)` 严格不等于 `dist(1,k)+dist(k,n)`。",
            "transformed_statement": "若存在可行赋权，可以把某条 1 到 n 的候选最短路边权都压到下界，其它边权都拉到上界；于是问题变成找一条不会被经过 k 的路线追平的绿色路径。",
            "key_observations": [
                "对任意可行赋权，取一条 1 到 n 的最短路 P；降低 P 上边权不会让经过 k 的最短路优势变大，升高 P 外边权也不会伤害 P。",
                "所以只需考虑 P 用下界、P 外用上界的极端赋权。",
                "固定 P 后，必要且充分条件是 P 上任意两点 u、v 满足 `d_L(u,v) < d_R(u,k)+d_R(k,v)`。",
                "这个条件可解释成强盗沿下界边走、警察沿上界边追；只需维护一个表示警察是否已被通知并能否追上的计时器。",
            ],
            "solution_brief": "关键观察：把可调实数边权压成一条下界路径和其它上界边。先从 k 用上界边权跑 Dijkstra 得到警察到各点距离 d；再从 1 跑改造 Dijkstra，状态值 t 表示当前危险计时器，过边 `(u,v)` 后变为 `max(t+l_i, -d_v)`。若处理某点时 `d_u<=t_u` 说明会被追上，丢弃；能处理到 n 则存在严格不经过 k 的最短路证据。",
            "primary_topic": "图论与网络流",
        },
        "2119F": {
            "statement_brief": "树根火山按深度逐层淹没。你从 st 出发，每个时刻先按当前点权 `+1/-1` 改生命，生命为 0 或当前位置被淹即死，然后必须走到相邻点。问最多能走几步。",
            "transformed_statement": "一条行走路线可看成从 st 到某个终点的主路径，加上若干在边上来回的折返段；难点是哪些折返真正有必要。",
            "key_observations": [
                "若路径不经过一条 `(1,1)` 边，则沿途点权必须在 `1` 和 `-1` 间交替，否则生命会提前归零。",
                "经过 `(1,1)` 边后，多个不同边上的折返都可以搬到第一次经过的 `(1,1)` 边处，不会破坏连通性、熔岩时限或生命下界。",
                "因此最优结构是：一条主路径，加上至多一个挂在主路径附近的可用 `(1,1)` 折返分支。",
                "可从所有 `(1,1)` 边出发，沿交替权值路径 BFS，预处理每个点到最近可用折返点的信息。",
            ],
            "solution_brief": "关键观察：把任意乱折返规整成“主路径 + 一个折返分支”。枚举终点 ed，先处理完全交替主路径的情况；若需要 `(1,1)` 折返，就用预处理得到主路径附近最近的可用折返点，并结合主路径上的最低生命值算最早可到达 ed 的时间。由于行走速度和熔岩速度相同，只需比较到达时间是否早于熔岩，再按奇偶补折返取最大步数。",
            "primary_topic": "树结构",
        },
        "2110D": {
            "statement_brief": "有向无环图的检查点按编号递增，点上可拿若干电池，边要求当前电池数至少为 w。电池不会消耗，问到达终点时携带电池数的最小可能值。",
            "transformed_statement": "二分最终电池上限 mid；在这个上限下，只需知道到达每个点时最多能有多少电池。",
            "key_observations": [
                "边只检查是否达到门槛，不消耗电池，所以携带越多越不差。",
                "固定答案上限 mid 后，到点 v 时可以把电池加上 `b_v`，再截断为 `mid`。",
                "若当前最大电池数小于边权 w，则这条边一定不能走；否则可以把同样电池数转移到终点。",
                "图边满足 `s<t`，天然拓扑序就是点编号顺序。",
            ],
            "solution_brief": "关键观察：答案可判定且单调。二分 mid，令 `dp[v]` 为在不超过 mid 的前提下到达 v 的最大电池数；从 1 到 n 顺序转移，先拿本站电池并截断，再尝试所有出边。若最终 `dp[n]` 可达，mid 可行；否则不可行。",
            "primary_topic": "动态规划与状态设计",
        },
        "2109C1": {
            "statement_brief": "交互题。隐藏整数 x 在 `[1,1e9]`，给定目标 n；最多 7 条命令，可加、乘、整除或把 x 变成数位和，要求把 x 变成 n。",
            "transformed_statement": "先用数位和把未知 x 压到极小范围，再利用失败不会改变 x 的加法命令做二进制式缩区间，最后加到 n。",
            "key_observations": [
                "第一次数位和后 `x<=81`，第二次数位和后 `x<=16`。",
                "`add -8` 若成功则把 `9..16` 映射到 `1..8`，若失败则原本就在 `1..8`，所以执行后一定在 `1..8`。",
                "继续执行 `add -4`、`add -2`、`add -1`，每次都把范围折半，最终必定得到 x=1。",
                "最后一条 `add n-1` 直接到目标值。",
            ],
            "solution_brief": "关键观察：交互返回值可当作条件赋值，但不用分支写复杂策略。固定输出 `digit, digit, add -8, add -4, add -2, add -1, add n-1`；前六步把任意初值压成 1，第七步到 n。",
            "primary_topic": "交互",
        },
        "2062B": {
            "statement_brief": "n 个时钟排成一行，每秒所有时钟先减一，若有时钟到 0 立即失败；之后你可移动到相邻位置或原地，并重置当前位置时钟。问能否无限坚持。",
            "transformed_statement": "长期策略只需要考虑沿整条线来回巡逻；每个位置 i 必须能等到你从最远端来回一次。",
            "key_observations": [
                "从位置 i 到左端再回来需要 `2(i-1)` 秒，到右端再回来需要 `2(n-i)` 秒。",
                "因为每秒先扣再重置，时钟初值必须严格大于这两个等待时间的最大值。",
                "所以必要条件是 `a_i > 2*max(i-1,n-i)`。",
                "若所有位置都满足，直接在 1 和 n 之间往返，路过时重置每个钟即可。",
            ],
            "solution_brief": "关键观察：不要寻找复杂路线，端点往返已经是最坏等待时间的上界。逐个检查 `a_i > 2*max(i-1,n-i)`；全满足输出 YES，否则某个时钟必然在最长回访间隔内归零，输出 NO。",
            "primary_topic": "构造与贪心",
        },
        "2040C": {
            "statement_brief": "对排列 p 定义所有子数组最小值之和 S(p)。要求输出使 S 最大的排列中字典序第 k 个；若不足 k 个则输出 -1。",
            "transformed_statement": "最大 S 的排列可以按数值从小到大构造：每个数只放在当前最左空位或最右空位。",
            "key_observations": [
                "放入当前最小未放数 i 时，它会成为所有以该位置为一端、只含未放大数的区间最小值，贡献固定为 `n-i+1`。",
                "若 i 不放在当前空段端点，把它移到端点且保持更大数相对顺序，未来由更大数形成的区间集合不会变差。",
                "因此最优排列必然先递增再递减，且每个 i 只有放左或放右两种选择。",
                "共有 `2^(n-1)` 个最优排列，可按二进制选择逻辑定位第 k 个。",
            ],
            "solution_brief": "关键观察：最优性先限制形态，再处理字典序。若 `k>2^(n-1)` 直接无解；否则从小到大决定每个数放左端还是右端，比较当前选择左端时能覆盖的方案数和 k 的关系，跳过相应块即可构造第 k 个最优排列。",
            "primary_topic": "构造与贪心",
        },
        "2035F": {
            "statement_brief": "根树每个点有非负值。第 i 次操作固定作用在编号 `((i-1) mod n)+1` 的点上，可把它子树内任一点加一或减一。问最少多少次后能把所有点变成 0，无解输出 -1。",
            "transformed_statement": "若 t 次可行，则 `t+2n` 次也可行：先给所有点整体加一再整体减一；所以可以按模 `2n` 的剩余类二分答案。",
            "key_observations": [
                "固定操作次数 x 后，每个点 i 作为操作根的次数 `has_i` 可 O(1) 算出。",
                "子树内的子节点需求必须先被满足，剩下的需求汇总到当前点。",
                "令 `dp[i]=子树 i 归零还需要父侧提供的净操作数`，则 `dp[i]=sum(dp[child])+a_i-has_i`。",
                "若 `dp[i]<0`，多余操作只能通过加减抵消浪费，最后只剩奇偶影响，即改成 `(-dp[i]) mod 2`。",
            ],
            "solution_brief": "关键观察：固定 x 的可行性是一次树形 DP。对每个模 `2n` 的剩余类二分 x；检查时后序遍历整棵树，按 `has_i` 和子树需求计算 dp，根的 dp 为 0 则这次操作数可行。题解再用“先压到非正”的下界给二分上界，避免无限大搜索。",
            "primary_topic": "树结构",
        },
        "2034F1": {
            "statement_brief": "袋子里有红宝石和蓝宝石，随机逐个抽出放入背包；当剩余数量命中特殊条件时，背包内所有宝石价值翻倍。求最终背包价值期望。",
            "transformed_statement": "把特殊条件从“箱子剩余数量”改写成“背包已拿数量”，并把随机过程看成从一个特殊状态走到下一个特殊状态的格路。",
            "key_observations": [
                "加入虚拟状态 `(0,0)` 和 `(n,m)` 后，按已拿总数排序所有特殊状态。",
                "`ways[i][j]` 表示从状态 i 到 j 且中间不经过其它特殊状态的抽取序列数，可用容斥扣掉中间特殊点。",
                "从 i 直接走到 j 时，不考虑翻倍的新增基础价值是 `2*红增量 + 蓝增量`。",
                "DP 记录到达每个特殊状态的所有路径价值总和，经过真实特殊状态时整体乘 2，最后除以总抽取序列数。",
            ],
            "solution_brief": "关键观察：期望不直接按每一步随机转移，而是按“特殊状态之间的段”聚合。先计算所有 `ways[i][j]`，再做状态 DP：从 j 转到 i 时，把已有价值加上这一段新增宝石价值，并在命中特殊状态后翻倍。最终用 `C(n+m,n)` 归一化得到期望。",
            "primary_topic": "组合计数与概率",
        },
        "2031B": {
            "statement_brief": "给一个排列，每次只能交换相邻且数值差恰好为 1 的两个元素，问能否排成升序。",
            "transformed_statement": "反过来从升序排列出发看可生成哪些排列：一旦交换了相邻值 i 和 i+1，这两个数就无法再和外侧继续交换。",
            "key_observations": [
                "从恒等排列中交换 `i,i+1` 后，左侧全小于 i，右侧全大于 i+1。",
                "此后 `i+1` 不可能再与左侧交换，i 也不可能再与右侧交换。",
                "所以所有发生过的交换必须互不相邻，最终排列只能由固定点和相邻反转对组成。",
                "检查时从左到右，遇到 `p_i=i` 跳过；遇到 `p_i=i+1,p_{i+1}=i` 就跳过这一对；其它情况无解。",
            ],
            "solution_brief": "关键观察：允许操作看似会冒泡，实际每个元素最多参与一次有效相邻反转。线性扫描排列，判断它是否能分解成若干 `i` 和 `(i+1,i)` 这样的块；能则 YES，否则 NO。",
            "primary_topic": "构造与贪心",
        },
        "2022A": {
            "statement_brief": "若干家庭坐一辆有 r 排、每排 2 座的车。同家庭两人同排会快乐，一个人单独坐一排也快乐。问最优安排下最多快乐人数。",
            "transformed_statement": "先尽量把同家庭成员两两成排；剩下的都是每个奇数家庭多出来的单人，问题变成这些单人能否各自独坐。",
            "key_observations": [
                "同家庭两人坐一排会产生 2 个快乐人，且用满一排，永远优先。",
                "设已成对人数贡献为 `2*pairs`，剩余单人数为 odd，剩余空排为 free。",
                "若 `free>=odd`，每个单人都能独坐，也都快乐。",
                "若 `free<odd`，必须把一些不同家庭单人塞同一排；剩余单人的快乐数变成 `2*free-odd`。",
            ],
            "solution_brief": "关键观察：座位安排只看成对数和奇数家庭数。统计 `pairs=sum(a_i/2)`、`odd=sum(a_i%2)`，基础答案为 `2*pairs`，剩余排数 `free=r-pairs`。若 free 足够，答案加 odd；否则加 `2*free-odd`。",
            "primary_topic": "构造与贪心",
        },
        "2239D": {
            "statement_brief": "统计所有无自环函数图的价值总和。一个大小为 m 的起点集合若能沿有向边覆盖所有点则成功，图的价值是成功集合数量。",
            "transformed_statement": "由于大小为 m 的集合对称，先固定一组关键点 S 计算它成为成功起点集的图数，最后乘以 `C(n,m)`。",
            "key_observations": [
                "在函数图的每个连通块中，若它是纯环，则环上至少要有一个关键点；若带入树，则所有入度为 0 的叶子都必须是关键点。",
                "对非关键点成为叶子、以及不含关键点的纯环做容斥。",
                "只需知道被指定成纯环的非关键点总数 i；多个无自环纯环带 `(-1)^环数` 的贡献和为 `g_i=1-i`。",
                "双重容斥求和后可化简成一重公式：固定关键集合的贡献为 `(n-1)*sum_k (-1)^k C(n-m,k)(n-k-1)^(n-1)`。",
            ],
            "solution_brief": "关键观察：不要枚举函数图，而是按固定起点集合做容斥。先用“纯环必须含关键点、非纯环叶子必须关键”刻画成功条件；枚举被容斥的非关键点集合，利用 `g_i=1-i` 合并纯环贡献，再把内层二项式和化成一重求和。最后把固定 S 的答案乘以 `C(n,m)`。",
            "primary_topic": "组合计数与概率",
        },
        "2255D": {
            "statement_brief": "给 n 个正整数。每秒选择一个位置向下取半，其它位置向上取半，问最少多少秒能让所有数都变成 0。",
            "transformed_statement": "固定总时间 T 后倒着看：第 s 秒选择某个位置，等价于给这个位置分配容量 `2^(s-1)`；问题变成把这些二进制容量分给各个需求 `a_i`。",
            "key_observations": [
                "若某个位置在若干秒集合 S 中被选中，则它能清零的充要条件是 `a_i <= sum_{s in S} 2^(s-1)`。",
                "每个正数至少要被选中一次，所以答案一定不小于 n。",
                "检查固定 T 时，把容量从大到小分给当前最大剩余需求是正确的：若最大需求超过当前容量，所有更小容量加起来也不够替代它。",
                "`a_i < 2^30`，因此超过 `2^30` 的大容量可以直接一对一清掉最大的若干需求，剩下最多只需模拟 30 个容量。",
            ],
            "solution_brief": "关键观察：不要模拟取整过程，而是倒推成容量分配。二分 T；每次检查先用所有不小于 `2^30` 的容量清掉最大需求，再把剩余需求放进堆里，用 `2^29...1` 贪心扣最大项。能分配则 T 可行，否则增大 T。",
            "primary_topic": "构造与贪心",
        },
        "2245B": {
            "statement_brief": "给数组 a 和操作费用 c。每次可删一个数得它的值，或删相邻两个数得较大值；每次操作都扣 c。问清空数组后的最大得分。",
            "transformed_statement": "先把每个数减去 c，则两种操作都等价于无费用版本中选择一个被计入得分的元素；核心是无费用时能实现哪些被选元素集合。",
            "key_observations": [
                "当 c=0 时，最终得分总是某个元素子集的和。",
                "任意大小 `k >= ceil(n/2)` 的目标子集都能通过删除操作实现：目标元素多于非目标元素时删单点，相等时一定能找到一对目标/非目标相邻并用双删吸收。",
                "因此无费用最优就是取至少 `ceil(n/2)` 个数，同时额外保留所有正数。",
                "有费用时令 `a'_i=a_i-c`，删单点得 `a'_i`，删双点得 `max(a'_i,a'_j)`，完全化回 c=0。",
            ],
            "solution_brief": "关键观察：费用不是额外维度，直接整体平移数组。把每个元素改成 `a_i-c` 后排序，设 `m=ceil(n/2)`、正数个数为 p，答案就是最大的 `max(m,p)` 个新值之和。",
            "primary_topic": "构造与贪心",
        },
        "2224B": {
            "statement_brief": "给非负数组，可任意重排。对每个前缀计算 MEX 和最大值，要求最大化所有前缀的 `MEX+max` 总和。",
            "transformed_statement": "最大值应该尽早出现；一旦最大元素放到第一位，后面的任务就是按能提升 MEX 的顺序摆剩余元素。",
            "key_observations": [
                "若最大值第一次出现在第 `i+1` 位，把它挪到首位会让前 i 个前缀最大值总贡献至少增加 i。",
                "这次移动造成的 MEX 总损失最多是前 i 个元素的 MEX，且该值不超过 i。",
                "所以存在最优方案把全局最大值放在第一位。",
                "剩余位置应优先放从 0 开始、当前还缺的最小值；无法继续提升 MEX 的重复值放到最后。",
            ],
            "solution_brief": "关键观察：先证明最大值放首位不会亏。之后按值统计，把 0、1、2... 中存在的最小缺口链尽早放出，让 MEX 尽快升高；剩余重复或过大的数只影响较晚前缀，放在末尾即可。按这个顺序模拟前缀 MEX 和 max 求和。",
            "primary_topic": "构造与贪心",
        },
        "2219A": {
            "statement_brief": "有 p 根单位直线段和 q 个单位 L 形块，要求全部用完拼成某个 `n*m` 网格；若可行输出任意尺寸，否则输出 -1。",
            "transformed_statement": "把所有零件都看成网格边：L 形块贡献两条互相垂直的边，直线段可用来补横纵边数量差。",
            "key_observations": [
                "`m*n` 个小格组成的网格总边数是 `m(n+1)+n(m+1)`，所以必须满足 `p+2q` 等于这个值。",
                "横边和竖边数量差为 `|m-n|`，只有直线段能补这个差，因此还必须有 `p>=|m-n|`。",
                "题解证明这两个条件也足够：两根直线段可以等价拼成一个 L，奇偶关系保证能把多余差值调整掉。",
                "假设 `m>=n`，由总边数可得 `n <= sqrt(p/2+q)`，枚举较小维度即可。",
            ],
            "solution_brief": "关键观察：可行性不是几何搜索，而是两条边数条件。枚举较小维度 n，若 `m=(p+2q-n)/(2n+1)` 是正整数，并且 `p>=|m-n|`，就输出这组尺寸；所有候选都失败则无解。",
            "primary_topic": "数论与同余",
        },
        "2215G": {
            "statement_brief": "在带连通障碍的方格迷宫中回答多组最短路。直走代价 2，斜走代价 3；障碍和外边界整体 4 连通。",
            "transformed_statement": "先把代价改写成直走 1、斜走 `sqrt(2)` 的几何距离，最后再把答案 `a+b*sqrt(2)` 映射回 `2a+3b`。",
            "key_observations": [
                "障碍整体连通且包住外边界，使可行区域的绕行结构可以通过若干方向的投影来刻画。",
                "直接在巨大网格上跑最短路不可行；题解改为看上、右、右上、左上四个方向投影的路径长度。",
                "四个投影量做线性组合后，原最短路查询会变成树上两点距离查询。",
                "真正的瓶颈因此不在网格最短路，而在为各个投影方向建树并支持 LCA 距离。",
            ],
            "solution_brief": "关键观察：把八方向加权距离拆成几个投影树距离。对每个方向把障碍切出的连续空段压成树节点，预处理深度和倍增 LCA；查询时找到起点、终点在各投影树上的节点，求四个树距，再按题解的线性组合还原为 `a+b*sqrt(2)`，最后输出 `2a+3b`。若某个方向不连通则不可达。",
            "primary_topic": "树结构",
        },
        "2196C1": {
            "statement_brief": "交互题。隐藏图是 DAG，需要通过询问按字典序排列的第 k 条路径来恢复所有有向边；简单版 n 小且询问次数较宽。",
            "transformed_statement": "每条边本身就是一条只含一条边的路径，所以可以在所有路径的字典序列表里逐个找出这些单边路径。",
            "key_observations": [
                "从某个起点出发的所有路径在字典序列表中形成可以按前缀跳过的连续块。",
                "对当前顶点，二分找到下一条长度为 1 且起点为该顶点的路径，就得到一条出边。",
                "找到一条出边后，所有以这条边为前缀的路径都不需要再看，可以继续二分下一条单边路径。",
                "对每个顶点重复这个过程，总询问数是 `O((n+m) log A)`，简单版 `A=2^30` 可以承受。",
            ],
            "solution_brief": "关键观察：恢复边不需要理解所有长路径，只抓每条边对应的单边路径。按顶点从小到大维护已经跳过的路径区间，用二分在第 k 条路径询问中找下一条单边路径；若找到就记录边并继续，否则转下一个顶点。",
            "primary_topic": "交互",
        },
        "2174B": {
            "statement_brief": "有 n 个朋友依次送卡，第 i 个最多送 `a_i` 张，总送卡数不超过 k。每个前缀的快乐值是目前收到的最大单次数，问最大总快乐。",
            "transformed_statement": "选择某个送卡数 x 时，把它放在最早能承载 x 的朋友处永远不差；因此原来的 n 个位置可压缩成按前缀最大值增长的至多 k 个关键位置。",
            "key_observations": [
                "朴素状态是处理到位置 i、已用总数 s、当前最大值 m 时的最大快乐值，但 `O(nk^3)` 太慢。",
                "若要使用 `b_i=x`，越早出现越能贡献更多前缀快乐，所以只需要保留 `a_i` 的前缀最大值变化点。",
                "压缩后位置数至多 k，因为容量只在 0..k 间变化。",
                "转移可反向写成当前最大值 m 是否在这一层被使用，并预处理 `max_t dp[s-m][t]` 去掉枚举 t。",
            ],
            "solution_brief": "关键观察：先把时间轴压缩，再把转移中的线性枚举拿掉。扫描 a 得到严格上升的前缀最大值序列；做三维 DP，状态为前若干关键位置、已用卡数、当前最大送卡数。每次用预处理最大值完成“上一层最大值任意”的转移，复杂度降为 `O(n+k^3)`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2163C": {
            "statement_brief": "给 `2*n` 网格，数值为 1..2n。对区间 `[l,r]`，只保留值在区间内的格子，问有多少区间存在从左上到右下的只向右或向下路径。",
            "transformed_statement": "固定左端 l 后，满足条件的最小右端 `r_l` 单调不降；于是可以双指针维护当前激活值域。",
            "key_observations": [
                "若 `[l,r]` 已经可行，扩大 r 只会激活更多格子，因此仍可行。",
                "当 l 增大时，激活格子只会减少，所以新的最小可行右端不会变小。",
                "在 2 行网格里，路径只需要选择一个下拐列：上排从 1 走到拐点，下排从拐点走到 n。",
                "令 a 为上排第一个未激活列，b 为下排最后一个未激活列；存在路径当且仅当 `a-1 > b`。",
            ],
            "solution_brief": "关键观察：二维路径判定可压成两个阻断位置。双指针枚举 l，持续增大 r 并激活对应格子；用两个有序集合维护上下两行未激活列，按 `a-1>b` 判断是否已有路径。得到每个 `r_l` 后贡献 `2n-r_l+1` 个右端，再移除值为 l 的格子。",
            "primary_topic": "构造与贪心",
        },
        "2157I": {
            "statement_brief": "两人轮流打 boss，每次造成 1..m 点伤害，但不能和对手上一招相同；先把血量打到 0 以下者胜。多组询问判断先手是否必胜。",
            "transformed_statement": "把状态写成 `(n,l)`：当前血量 n，且本手不能打 l。核心是研究固定 n 时有多少个 l 会让状态必败。",
            "key_observations": [
                "若 `(n,l)` 必败，则 `(n+l,l')` 对任意 `l'!=l` 都是必胜；这限制了同一个 n 的必败禁招数量。",
                "固定 n 时，必败的 l 数量只能是 0、1 或 `m+1`，题解分别称为 良好、中性、邪恶。",
                "邪恶血量很稀疏；相邻邪恶血量的距离至少是 `m+1`，奇数 m 时进一步落在 `m+1` 或 `m+2`。",
                "偶数 m 可直接判 `m+1` 的倍数；奇数 m 只需生成邪恶血量序列，并用少数候选递归判断下一项。",
            ],
            "solution_brief": "关键观察：不要按 n、上一招暴力博弈 DP，而是只维护邪恶血量。偶数 m 时必败点就是 `m+1` 的倍数；奇数 m 时从当前邪恶血量 `v_i` 出发，只需判断 `v_i+m+1` 是否邪恶，否则下一项为 `v_i+m+2`。题解给出平均 O(1) 的递归判定，所以总复杂度按邪恶血量数量约为 `O(N/m)`。",
            "primary_topic": "博弈",
        },
        "2154F1": {
            "statement_brief": "给一个含 -1 的长度 n 排列，问有多少种补全方式能成为有序排列 `1..n` 的 交错洗牌；简单版 `n<=3000`。",
            "transformed_statement": "固定 分割点 k 后，值 `<=k` 和 `>k` 分成两种颜色，合法性等价于两种颜色各自按数值递增出现在排列中。",
            "key_observations": [
                "除完全有序排列外，合法排列的 分割点 k 可由第一对满足 k 出现在 k+1 后面的相邻数值唯一确定。",
                "固定 k 后，对蓝色值 x，它出现处的前缀里必须正好有 x 个蓝色；对红色值 x，前缀里必须正好有 `x-k` 个红色。",
                "已知位置给出每段缺失颜色数量的硬约束，剩余 -1 只是在段内选择哪些位置放蓝/红。",
                "每段方案数是组合数，预处理阶乘后可 O(1) 查询；枚举所有 k 得到 O(n^2)。",
            ],
            "solution_brief": "关键观察：先按 分割点给数值染色，再数位置染色。枚举 k，扫描已有数值，按其颜色和数值推导当前前缀中该颜色应有多少个，从而确定当前空段要填多少蓝/红；用组合数乘起来。最后注意完全有序排列可能被多次计数，需要单独扣重。",
            "primary_topic": "组合计数与概率",
        },
        "2154C2": {
            "statement_brief": "给数组 a 和每个位置加一的费用 b。可给任意位置加任意次，求最小费用使某两个数的 gcd 大于 1；困难版费用可很大。",
            "transformed_statement": "因为总能把两个数都调成偶数，答案有上界 `b_i+b_j`；这会强力限制需要考虑的多次加法位置。",
            "key_observations": [
                "若两个位置都加超过一次，不会优于把它们都调成偶数的方案。",
                "因此要么每个候选位置只加 0 或 1 次，要么只有费用最小的那个位置可能加多次。",
                "0/1 次情况可用质因子计数判断：已有公共质因子答案为 0；某个 `a_i+1` 与其它数共享质因子则可用一次费用。",
                "多次加法只需枚举其它数的质因子 p，计算最小费用位置加到 p 的倍数需要多少步。",
            ],
            "solution_brief": "关键观察：高费用版本不是最短路，而是先用“调成偶数”的上界剪掉绝大多数多次操作。按 b 排序取最小费用位置 idx；先检查不加和单次加的公共质因子，再对其它所有数的质因子 p 计算 `idx` 加到 p 倍数的代价，三类方案取最小。",
            "primary_topic": "数论与同余",
        },
        "2146B": {
            "statement_brief": "给 n 个集合，元素范围为 1..m。问选择若干集合覆盖所有元素的方案数是否至少为 3。",
            "transformed_statement": "若全集都不能覆盖，答案显然否；否则“选择所有集合”已经是一种方案，只需判断删掉一个集合后是否还有至少两种覆盖方案。",
            "key_observations": [
                "所有元素至少出现一次时，全选集合一定可行。",
                "若存在至少两个不同集合可以被删除后仍覆盖全集，那么全选和这两种 `n-1` 选择已经给出至少三种方案。",
                "若至多一个集合可删除，则不可能存在更少集合的覆盖；否则从那个更小方案补回不同未选集合，会产生至少两个 `n-1` 方案。",
                "所以只要统计每个元素出现次数，并逐个测试删除一个集合是否会让某个元素次数归零。",
            ],
            "solution_brief": "关键观察：不用真的计数所有覆盖，只判定可删集合数量。先统计每个元素出现次数，若有 0 则 NO；然后枚举集合 i，临时把其中元素计数减一，看是否出现 0。可删除集合数至少 2 则 YES，否则 NO。",
            "primary_topic": "构造与贪心",
        },
        "2108D": {
            "statement_brief": "交互题。隐藏数组 C 由两个长度都至少为 k 的数组 A、B 拼接而成；A 和 B 中任意连续 k 个数都是 `1..k` 的一个排列。要求确定 A、B 的长度，若不能唯一确定则输出 -1。",
            "transformed_statement": "先询问最左 k 个和最右 k 个，得到 A、B 在模 k 位置上的两个排列；若某个模位置两边值不同，就能沿这个模位置二分拼接边界。",
            "key_observations": [
                "A、B 内部每 k 个连续元素都是排列，因此同一个数组在相同模 k 位置上的值固定。",
                "若左右两端的标准排列完全相同，除非 `n=2k`，否则边界无法唯一确定。",
                "找到一个左右值不同的模位置后，沿这些同余位置二分即可定位边界所在的 k 块。",
                "最后只需在边界附近、那些左右排列不同的位置上再二分；若中间存在无法归属的空白区间，则答案不唯一。",
            ],
            "solution_brief": "关键观察：不要逐点找断点，而是利用长度 k 的排列周期。询问前 k 位和后 k 位，比较两个模 k 排列；若没有差异就按是否 `n=2k` 判定。否则选一个差异位置，在同余类上二分出从 A 模式切到 B 模式的相邻块，再在这 k 个位置内二分精确边界；若精确边界不是唯一相邻位置，输出 -1。",
            "primary_topic": "交互",
        },
        "2096E": {
            "statement_brief": "一排玩具熊只有黑色和粉色。一次操作可选连续三个位置并把其中黑色排到左边、粉色排到右边。问最少几次操作能让所有黑熊在所有粉熊左边。",
            "transformed_statement": "把黑熊看成 0、粉熊看成 1；操作就是排序长度为 3 的二进制窗口，目标是把整个二进制串排序。",
            "key_observations": [
                "一次操作按形态分为四类，其中两类能减少 2 个逆序，另外两类只减少 1 个逆序。",
                "若初始逆序数为 x，答案至少为 `ceil(x/2)`。",
                "只用减少 2 个逆序的操作会让剩余中间段呈 1010... 的交替形态，接下来必须考虑位置奇偶。",
                "令 a 为黑熊总数、b 为偶数位置黑熊数；最终排序后 b 必须等于 `floor(a/2)`，差值 d 只能靠减少 1 个逆序的操作修正。",
            ],
            "solution_brief": "关键观察：答案由逆序数和黑熊奇偶位置偏差共同决定。统计粉在黑左侧形成的逆序数 x，再统计黑熊总数 a 和偶位黑熊数 b，令 `d=abs(floor(a/2)-b)`。必须做 d 次一逆序操作修正奇偶，其余逆序都能两两消掉，答案为 `(x+d)/2`。",
            "primary_topic": "构造与贪心",
        },
        "2092B": {
            "statement_brief": "给两个长度为 n 的 01 串 a、b。一次可交换 `a_i` 与 `b_{i-1}`，或交换 `b_i` 与 `a_{i-1}`。问能否通过任意次交换让 a 全为 0。",
            "transformed_statement": "交换只在两条交错链内部移动字符：`a_1,b_2,a_3,...` 和 `b_1,a_2,b_3,...`，两条链互不影响。",
            "key_observations": [
                "每种操作都只会在某一条交错链上交换相邻元素。",
                "同一条链内通过相邻交换可实现任意重排，但 0 和 1 的数量不变。",
                "要让 a 全为 0，第一条链需要至少容纳 a 的奇数位数量个 0，第二条链需要至少容纳 a 的偶数位数量个 0。",
                "因此两个交错链中的 0 数分别至少为 `ceil(n/2)` 和 `floor(n/2)`。",
            ],
            "solution_brief": "关键观察：不要模拟交换，把位置分成两条斜向链。统计链 1 中的 0 数和链 2 中的 0 数；若链 1 至少有 `(n+1)/2` 个 0 且链 2 至少有 `n/2` 个 0，就能把这些 0 重排到 a 的所有位置，否则不行。",
            "primary_topic": "构造与贪心",
        },
        "2077F": {
            "statement_brief": "给数组 a、b，可任意次把某个元素加一。要求最少加几次后，使 a 能通过若干次 `AND x` 与 `OR x` 的双点操作变成 b。",
            "transformed_statement": "先刻画目标 pair 何时可达：要么两数组相等，要么目标数组中存在两个不同位置，使一个值是另一个值的子掩码。",
            "key_observations": [
                "若最终 a 不等于 b，最后一次双点操作会在目标数组中留下一个子掩码和一个超掩码。",
                "反过来，一旦目标 b 中有这样一对子掩码/超掩码，就能用固定操作序列把其它位置逐个调整好。",
                "相等方案的代价是把每一对 `a_i,b_i` 都加到二者最大值，即 `sum |a_i-b_i|`。",
                "非相等方案可建值域图：加一是有代价边，走向子掩码表示建立可达关系；从所有 b 值出发求两种最近颜色即可找最小额外代价。",
            ],
            "solution_brief": "关键观察：复杂位运算操作先变成目标数组中的子掩码关系。答案取两类方案最小：一类把 a、b 对齐；另一类是在 b 的值域上找最便宜方式，让两个不同位置的值变成子掩码和超掩码。实现用 DP 在值域图上传播每个点最近和次近的原始 b 值，经过加一边、子掩码边和反向加一边三轮转移。",
            "primary_topic": "动态规划与状态设计",
        },
        "2034G1": {
            "statement_brief": "给若干实数时间段染色。任意被至少一个区间覆盖的时刻，都必须存在一种颜色恰好覆盖一次。求最少颜色数并构造染色。",
            "transformed_statement": "先尝试 1 色和 2 色；若 2 色贪心失败，题解给出总能用 3 色覆盖的构造。",
            "key_observations": [
                "1 色可行当且仅当任意时刻最多只有一个区间覆盖。",
                "验证 G1 的实数点时，只需把端点乘 2，把整数点和半整数点统一成离散整数点处理。",
                "2 色贪心按左端点排序扫描，维护两种颜色当前未结束的区间数量和最早结束区间。",
                "若某个时刻两种颜色的覆盖次数都不是 1，则 2 色不可能；否则贪心给出的染色合法。",
            ],
            "solution_brief": "关键观察：判定条件只关心每个时刻各颜色的活跃数量是否有一个等于 1。先离散化端点；扫描区间尝试 2 色，按当前两色活跃数量和最早结束点决定新段颜色，一旦出现两色活跃数都不为 1 的坏状态就放弃。放弃后使用题解的 3 色覆盖构造：交替选覆盖最左未处理点且右端最远的区间染 1/2，其余补 3。",
            "primary_topic": "构造与贪心",
        },
        "2024B": {
            "statement_brief": "自动售货机有 n 个按钮和 n 个槽位，但按钮标签未知。已知每个槽初始有多少罐，按空槽按钮不会出货且无法知道对应槽位。问保证拿到至少 k 罐最少要按几次。",
            "transformed_statement": "在还没失败的按钮中，最稳妥策略是优先按当前被按次数最少的按钮；排序后按库存层数一层层推进。",
            "key_observations": [
                "某个按钮按出空后，再按它没有意义。",
                "未失败按钮彼此不可区分，按次数越少的按钮越值得优先尝试。",
                "把库存排序为 `a1<=a2<=...<=an` 后，前 `a1` 轮按所有按钮一定都成功。",
                "每跨过一个库存层，若还没拿够 k 罐，就必须额外承受一次可能按到已空按钮的失败。",
            ],
            "solution_brief": "关键观察：答案是成功的 k 次加上不可避免的失败层数。排序库存，从小到大累计每一层能保证拿到的罐数 `(a_i-a_{i-1})*(n-i+1)`；找到第一次累计达到 k 的层。此前已经跨过的不同库存层数就是额外失败次数 x，输出 `k+x`。",
            "primary_topic": "构造与贪心",
        },
        "2018F3": {
            "statement_brief": "统计所有长度为 n、取值在 `[1,n]` 的 deadline 数组；对每个 k，要求计数 D1B 中允许获胜的起始城市数恰好为 k 的数组数量。",
            "transformed_statement": "获胜起点要么不存在，要么正好是一段交集区间 `I=∩[i-a_i+1,i+a_i-1]`；困难版需要把按区间计数的 DP 压到 `O(n^2)`。",
            "key_observations": [
                "若某个起点可赢，题解的确定性策略足够：右侧有正好卡 deadline 的城市就先向右，否则向左。",
                "所有可赢起点构成空集或一个连续区间 I，且 I 给出下界 `a_i>=max(i-l+1,r-i+1)`。",
                "先按区间 I 计数，再用二维差分/容斥扣掉更大的可赢区间，可得到恰好 I 的数组数。",
                "困难版把左端和右端约束分开，在反向时间 DP 中隐式确定左端，把总状态降到 `O(n^2)`。",
            ],
            "solution_brief": "关键观察：计数对象不是起点，而是“可赢起点区间”。利用区间交集刻画所有可赢起点；对固定右边界形态反向模拟确定性策略，DP 记录当前已访问区间和下一步是否被迫向右。最后通过区间容斥得到恰好长度 k 的贡献，`k=0` 用 `n^n` 减去非空区间贡献。",
            "primary_topic": "动态规划与状态设计",
        },
        "2018F2": {
            "statement_brief": "中等版同样要求对每个 k 统计 deadline 数组，使 D1B 中获胜起始城市数恰好为 k。",
            "transformed_statement": "在固定可赢区间长度 k 后，把所有可能位置的约束嵌入长度 `2n` 的统一 bound 数组里，避免为每个区间单独重跑 DP。",
            "key_observations": [
                "可赢起点仍然只能是空集或连续区间 I。",
                "固定 I 后，`a_i` 有下界 `max(i-l+1,r-i+1)`，确定性访问策略可转成区间 DP。",
                "对同一个长度 k，不同位置的 bound 数组只是统一长数组中的长度 n 子段。",
                "因此每个 k 只跑一次更大的 DP，再读取所有窗口答案，复杂度从按区间重跑降一层。",
            ],
            "solution_brief": "关键观察：相同长度的可赢区间共享同一种约束形状。枚举 k 时，在长度 `2n` 的循环式 bound 数组上跑区间 DP，`dp[i][i+n-1]` 就对应某个实际区间位置。再做区间容斥扣掉包含更大可赢区间的情况，得到每个 k 的计数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2018F1": {
            "statement_brief": "简单版要求对每个 k 统计 deadline 数组，使原 Speedbreaker 问题中恰好有 k 个可获胜起始城市。",
            "transformed_statement": "先枚举非空可赢起点区间 I，再统计哪些 deadline 数组至少让 I 中所有起点可赢，最后用容斥得到恰好 I。",
            "key_observations": [
                "对固定起点，题解给出一个足够的确定性策略；若存在任意获胜策略，这个策略也能赢。",
                "所有获胜起点不是零散集合，而是空集或一个连续区间 I。",
                "固定 I 后，每个城市 deadline 至少为它到 I 两端的最大距离加一。",
                "区间 DP 统计 `(deadline 数组, 访问顺序)`，再除以区间长度消掉同一数组对应的多个起点。",
            ],
            "solution_brief": "关键观察：把“多少起点能赢”转成“哪个区间整体能赢”。简单版 n 小，可以枚举 I，按确定性策略做区间 DP：从已访问区间扩到左端或右端，并检查新城市 deadline 下界。得到至少包含 I 的计数后，用二维容斥扣掉更大区间，最后按区间长度汇总；k=0 用总数减去所有非空贡献。",
            "primary_topic": "动态规划与状态设计",
        },
        "2018E2": {
            "statement_brief": "给 n 条闭区间。若能把选中的区间分成若干等大小组，并且两区间相交当且仅当它们在同一组，则该集合复杂。困难版求最大复杂子集大小。",
            "transformed_statement": "固定每组大小 m 时，问题是最多能贪心取出多少组两两互不相交的区间簇；困难版把原本线段树维护的最大覆盖值改成 DSU 维护后缀最大位置。",
            "key_observations": [
                "先把端点扰动成互不相同，同时保持区间相交关系不变。",
                "按右端点扫描，遇到不与上一组冲突的区间就在 `[l,r]` 上加一；某点累计到 m 就形成一组。",
                "线段树里的最大值可换成“后缀最大位置”的二进制串表示。",
                "区间右端推进时批量清零，左端影响只会落到左侧最近的 1；这个最近 1 可用 DSU 维护。",
            ],
            "solution_brief": "关键观察：外层仍枚举或分治每组大小 m，但核心 `max_k(m)` 要降掉 log。把扫描过程中的覆盖数组压成后缀最大标记：位置大于当前 r 的仍为 1，位置不大于 r 的只有作为后缀最大才为 1。加区间时清掉失效范围，并用 DSU 找左侧最近 1 更新组件数，由此近似线性求出固定 m 的组数。",
            "primary_topic": "数据结构",
        },
        "2018E1": {
            "statement_brief": "给 n 条闭区间。若选中区间可分成若干等大小组，且区间相交当且仅当同组，则集合复杂。简单版求最大复杂子集大小。",
            "transformed_statement": "固定每组大小 m，贪心求最多能组成多少组 k；答案最大化 `m*k`，再利用 `m*k<=n` 做根号分治。",
            "key_observations": [
                "对固定 m，可按右端点排序扫描，用懒标记线段树维护当前可组成组的交点覆盖次数。",
                "当某个点被 m 个候选区间覆盖时，这 m 个区间可以形成一个组，然后开始找下一组。",
                "若固定组数 k，可二分最大的 m，使 `max_k(m)>=k`。",
                "因为 `m*k<=n`，要么 m 小、要么 k 小；按阈值分治可通过 简单版限制。",
            ],
            "solution_brief": "关键观察：先解决“固定组大小能取几组”。实现 `max_k(m)`：按右端点扫区间，对不和上一组选出的区间冲突的候选在 `[l,r]` 加一，最大值达到 m 就记一组并重置相关限制。然后对小 m 直接算，对小 k 二分 m，取最大 `m*k`。",
            "primary_topic": "数据结构",
        },
        "2018B": {
            "statement_brief": "n 个城市排成一行，选一个起点后每次只能扩展到已占领区间相邻城市；城市 i 必须不晚于 `a_i` 时刻被占领。问有多少起点能获胜。",
            "transformed_statement": "起点 x 等价于把 `a_x` 设为 1；对每个时刻 t，所有 deadline 不超过 t 的城市必须已经包含在长度不超过 t 的区间内。",
            "key_observations": [
                "令 `[l,r]` 为所有 `a_i<=t` 的城市的最小覆盖区间；若长度大于 t，则任何起点都不可能满足。",
                "若选择起点 x 后，新的最小区间可能变成 `[x,r]`、`[l,x]` 或保持不变，都必须长度不超过 t。",
                "由此 x 必须落在 `[r-t+1,l+t-1]`。",
                "把所有 t 对 x 的限制区间取交，交集长度就是可行起点数。",
            ],
            "solution_brief": "关键观察：不需要逐个起点模拟扩展。按 deadline 从小到大维护当前必须及时占领的最小区间 `[l,r]`；每加入一个城市就得到一条对起点 x 的限制 `[r-t+1,l+t-1]`，不断取交。若某次 `[l,r]` 自身长度已经超过 t，则答案为 0；否则最终交集大小就是答案。",
            "primary_topic": "构造与贪心",
        },
        "2209D": {
            "statement_brief": "给红、绿、蓝三种数量，要求构造尽量长的颜色串，使相邻位置颜色不同，且相距 3 的两个位置颜色也不同。",
            "transformed_statement": "合法串的结构可以看成若干“异色二元组”再加至多一个单点；因此先决定最多能拿多少个球，再按配对顺序排出来。",
            "key_observations": [
                "若连续三个颜色都不同，那么第四个颜色会被前两个限制到只能等于第二个。",
                "于是构造等价于不断把两个不同颜色配成一组，最后最多剩一个单独颜色。",
                "一个选中集合合法的必要充分条件是任一颜色数量不超过总数的一半向上取整。",
                "实际构造时每次取当前剩余最多的两种颜色配对，再把单点和三类配对按避免首尾冲突的顺序展开。",
            ],
            "solution_brief": "关键观察：别直接搜字符串，先把它压成异色配对问题。每轮取剩余最多的两种颜色组成一对，直到不能配；若还能放一个单点就放在最前面。最后按题解要求排列各类配对，特别处理单点颜色相同的配对，避免 `r=g=b=2` 这类边界冲突。",
            "primary_topic": "构造与贪心",
        },
        "2197A": {
            "statement_brief": "定义 `d(y)` 为十进制数位和，若 `y-d(y)=x` 则称 y 对 x 友好。给定 x，求友好数 y 的数量。",
            "transformed_statement": "因为 `y-x=d(y)`，候选 y 只可能比 x 大一个很小的数位和；题解证明检查 `[x,x+83]` 足够。",
            "key_observations": [
                "`y-d(y)=x` 等价于 `y=x+d(y)`，所以 y 不会离 x 太远。",
                "对本题范围内可能相关的数，十进制数位和最大只需按 83 这个常数上界考虑。",
                "因此不用反推 y，只需暴力枚举 x 到 x+83。",
            ],
            "solution_brief": "关键观察：候选空间是常数级。对每个测试用例枚举 `y` 从 `x` 到 `x+83`，直接计算 `y-数位和(y)` 是否等于 x，计数即可。",
            "primary_topic": "基础实现与模拟",
        },
        "2196E1": {
            "statement_brief": "给源串 `s` 和目标串 `t`。一次操作可复制 `s` 的一个子串接到当前串末尾，并允许修改这段中至多一个字符。求拼出 `t` 的最少操作数。",
            "transformed_statement": "每一步贪心取当前 `t` 剩余前缀中，能被 `s` 的某个子串匹配且至多一处不同的最长前缀。",
            "key_observations": [
                "取更短前缀不会让下一段变长，因此最长可行前缀贪心是正确的。",
                "对短段，用根号分治预处理 `s` 中短子串删去一个字符后的哈希，快速判断一处修改匹配。",
                "对长段，枚举 `s` 中起点，用后缀数组或哈希求两段 LCP，跳过第一处不等后再接一段 LCP。",
                "阈值 B 平衡短段预处理和长段枚举，简单版取常数约 50 即可。",
            ],
            "solution_brief": "关键观察：答案是把 t 切成若干最长“近似出现”的块。维护当前起点 l，求最大 r 使 `t[l..r]` 与 `s` 某子串至多一处不同；短长度用删一位哈希集合查，长长度枚举源串起点并用 LCP 计算可延伸长度。每次切掉最长块，切块次数就是答案。",
            "primary_topic": "字符串",
        },
        "2189D2": {
            "statement_brief": "给含 `0/1/?` 的串 s 和整数 c。把问号补成二进制串 w 后，`f(w)` 是 D1 中给出的乘积式；要求找到不被 c 整除的最小 `f(w)`，或判不存在。",
            "transformed_statement": "固定字符先形成乘积 b；剩余问号位置各自在因子 `2` 和 `i-1` 中选一个，目标变成让剩余乘积 x 最小且不被 `c/gcd(b,c)` 整除。",
            "key_observations": [
                "已固定部分只通过 `gcd(b,c)` 影响整除性，可以逐项约掉以避免乘积溢出。",
                "若 `s_2` 可选，应选成 1，因为对应因子为 1，不增大答案也不会引入新的整除风险。",
                "若化简后的模数 `c'` 不是 2 的幂，全选最小因子 2 就已经不会被 `c'` 整除。",
                "若 `c'` 是 2 的幂，需要控制最终乘积中的 2 因子个数；优先把较大的可选 j 替换成 2 以尽量减小乘积。",
            ],
            "solution_brief": "关键观察：所有选择都落在乘法因子上。先用固定字符把 c 化成 `c'`；若不存在自由选择也直接判断。对问号位置收集可选的 `j=i-1`，按题解分两类：`c'` 非 2 幂时全部取 2；`c'` 为 2 幂时在不让 x 被 `c'` 整除的前提下，贪心把最大的 j 改选为 2，最后乘回固定部分得到最小值。",
            "primary_topic": "数论与同余",
        },
        "2175B": {
            "statement_brief": "给 `n,l,r`，要求构造正整数数组 a，使且仅使子数组 `[l,r]` 的异或和为 0，所有其它非空子数组异或和都非零。",
            "transformed_statement": "把 a 转成前缀异或数组 b；子数组异或为 0 当且仅当对应两个前缀异或相等。",
            "key_observations": [
                "`xor(l,r)=b_r xor b_{l-1}`，因此目标是只让 `b_r=b_{l-1}` 这一对前缀相等。",
                "其它所有前缀值必须两两不同，否则会额外产生零异或子数组。",
                "最简单做法是令 `b_i=i`，唯独把 `b_r` 改成 `l-1`。",
                "最后由 `a_i=b_i xor b_{i-1}` 还原原数组。",
            ],
            "solution_brief": "关键观察：唯一零异或区间对应唯一一对相等前缀。构造前缀异或 `b_0=0`，对所有 i 先设 `b_i=i`，再令 `b_r=l-1`。然后输出 `a_i=b_i xor b_{i-1}`；这样只有 `[l,r]` 的两端前缀相等。",
            "primary_topic": "构造与贪心",
        },
        "2161D": {
            "statement_brief": "数组 b 若不存在 `i<j` 且 `b_j-b_i=1`，则称为好数组。给数组 a，求最少删除多少元素后剩余序列变好。",
            "transformed_statement": "等价于保留最多元素。把元素按值升序、同值按下标降序排序后做 DP，唯一需要禁止的是值差 1 且原下标顺序会形成坏对的转移。",
            "key_observations": [
                "同值之间不会产生差 1，可以一起保留；值差至少 2 的元素也互不冲突。",
                "只有从值 x 到值 x+1 时要看原数组下标：若 x 在前、x+1 在后，就会形成坏对。",
                "排序后设 `dp[i]` 为以第 i 个排序元素结尾时最多保留数，转移只需排除上一值且下标更小的状态。",
                "维护值小于等于 `x-2` 的全局最大、值等于 `x-1` 的下标后缀最大、以及同值最大，可把转移降到线性或对数级。",
            ],
            "solution_brief": "关键观察：这是最长可保留子序列，而不是局部删相邻。把 `(a_i,i)` 按值升序、同值下标降序排列；处理当前值 x、下标 pos 时，可从值不超过 x-2 的任意状态转移，也可从同值转移，还可从值 x-1 但下标大于 pos 的状态转移。取最大保留数 M，答案为 `n-M`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2157A": {
            "statement_brief": "若数组中每个出现过的整数 x 都恰好出现 x 次，则数组平衡。给数组 a，问最少删多少元素使其平衡。",
            "transformed_statement": "每个数值互相独立：值 x 最终只能保留 0 个或恰好 x 个。",
            "key_observations": [
                "若 x 的出现次数 `f[x]` 小于 x，则不可能补元素，只能全部删掉。",
                "若 `f[x]>=x`，最优是保留 x 个，删除多余的 `f[x]-x` 个。",
                "所有值的贡献直接相加即可。",
            ],
            "solution_brief": "关键观察：没有跨值约束。统计每个值 x 的频率 f；若 `f<x`，答案加 f；否则答案加 `f-x`。总和就是最少删除次数。",
            "primary_topic": "基础实现与模拟",
        },
        "2152H2": {
            "statement_brief": "给一棵带边权树。对每个查询 l，要求选择非负点权，使任意非空红色集合的最小割式代价至少为 l，并最小化点权总和。",
            "transformed_statement": "题解把固定 l 的计算写成树形递推；困难版要把每个子树答案视为关于 l 的凸分段线性函数并整体维护。",
            "key_observations": [
                "固定 l 时，叶子满足 `dp_v=max(0,l-f_v)`，内部节点满足 `dp_v=max(dp_a+dp_b,l-f_v)`。",
                "`dp_v(l)` 始终是斜率非降的凸分段线性函数。",
                "两个子函数相加等价于合并断点集合；再与直线 `l-f_v` 取 max 时，只会删掉交点以下断点并新增常数个断点。",
                "用可并堆或小到大合并维护断点，最后按查询 l 求根函数值。",
            ],
            "solution_brief": "关键观察：不要对每个查询重新跑树 DP，而是把 DP 结果作为函数预处理出来。每个节点维护函数斜率变化的断点堆；合并孩子时合并断点，应用 `max` 操作时找到与直线的交点并截断旧函数。所有断点总增量可摊还控制，查询时在根函数上求值即可。",
            "primary_topic": "数据结构",
        },
        "2150E1": {
            "statement_brief": "交互题。隐藏数组长度 `2n-1`，数 `1..n` 中只有一个数出现一次，其它都出现两次；一次询问集合 S 和值 x，回答 S 中是否存在 x。要求找出单独出现的数。",
            "transformed_statement": "递归二分下标区间，并维护哪些值只在当前区间内、哪些值在区间内外各出现一次；每次用询问判断它们落在左右哪边。",
            "key_observations": [
                "若假装所有值都出现两次，某个半区按值归属推算出的长度会和真实半区长度不一致。",
                "这个长度不一致的半区一定包含单独出现的值。",
                "`vals` 中的值需要询问左右两边是否出现；`waste` 中的值只需判断它在当前区间内的那一次落在哪边。",
                "递归深度为对数，每层询问数与当前区间长度同阶，满足版本 1 的询问上限。",
            ],
            "solution_brief": "关键观察：用“所有数都成对出现”的假设制造矛盾。递归处理 `[tl,tr]`，把它拆成左右半区；对相关值询问它们是否出现在左右半区，并据此计算如果全成对时左右应有的元素数。与真实长度不符的一侧包含答案，更新 `vals/waste` 后继续递归，区间变成单点时得到隐藏单值。",
            "primary_topic": "交互",
        },
        "2147H": {
            "statement_brief": "给无向带正容量图。若某个诱导子图的任意两点最大流值都有共同因子 `d>=2`，则称它好。要求用最少颜色给点染色，使每个颜色诱导子图都好。",
            "transformed_statement": "先判断整图是否已经好；否则题解证明 2 色总够，只需让每个颜色内部所有奇容量边的割都是偶数。",
            "key_observations": [
                "答案为 1 可用 Gomory-Hu 树求全点对最小割，再检查这些最大流值是否有共同因子。",
                "若答案不是 1，丢掉偶容量边后，只需把奇容量边按点度奇偶构造一个两色划分。",
                "若一个诱导子图中每个点的奇容量边度数为偶数，则任意割的奇边数为偶数，最小割值也为偶数。",
                "构造两色划分时，可递归删除奇度点，把它的邻居两两连辅助边，回溯时给该点选一种颜色以恢复偶度条件。",
            ],
            "solution_brief": "关键观察：最大流条件可降到割值奇偶。先用 Gomory-Hu 判断是否一色可行；若不可行，只看奇容量边。递归消去奇度点并在邻居间加辅助边，剩余图染好后回溯放回该点，选择能让同色诱导子图中奇边度数保持偶数的颜色。这样构造出 2 色最优解。",
            "primary_topic": "图论与网络流",
        },
        "2129A": {
            "statement_brief": "给若干不同线段，把选中线段同时看成数轴区间和图边。目标最大化区间并长度减去处在简单环上的点数，并输出一组最优线段。",
            "transformed_statement": "最优解可以假设图中没有环；如果选集里有环，删掉环上一条线段不会减少区间并长度，却会降低环惩罚。",
            "key_observations": [
                "最优选集中 `g(S)` 可以压到 0，否则去掉环上一条边不会损失覆盖长度。",
                "为了保持最大覆盖长度，只需保留不被其它线段完全包含的线段。",
                "删掉所有被包含线段后，若剩余图还有长度至少 3 的环，环上某个峰值点会推出一条相邻线段包含另一条，矛盾。",
                "因此 O(n^2) 标记被包含线段，保留剩余线段就是一种最优解；也可用 DSU 维护森林。",
            ],
            "solution_brief": "关键观察：惩罚来自环，而被包含线段对区间并没有贡献。遍历每条线段，若它被另一条线段完全包含则不选；否则保留。保留下来的线段覆盖了原集合的全部区间并，并且题解证明不会形成简单环，因此 `f-g` 最大。",
            "primary_topic": "构造与贪心",
        },
        "2110F": {
            "statement_brief": "定义数组美丽值为所有数对中 `(x mod y)+(y mod x)` 的最大值。给数组 a，要求输出每个前缀的美丽值。",
            "transformed_statement": "任意最优数对都可以换成包含当前前缀最大值的数对；因此维护前缀最大值并只在最大值大幅翻倍时重新扫历史。",
            "key_observations": [
                "对任意 x、y，`f(x,y)` 不超过二者最大值。",
                "若某个最优对不含前缀最大值 M，把较大那个数与 M 配对不会更差。",
                "若新最大值 `a_i` 小于旧最大值的两倍，则它和旧最大值配对直接得到 `a_i`，答案达到上界。",
                "只有当新最大值至少翻倍时，才需要枚举历史元素；这种情况最多发生 `log A` 次。",
            ],
            "solution_brief": "关键观察：前缀答案只需要围绕最大值更新。扫描数组维护当前最大值 M 和答案 ans；若新数不超过 M，用它和 M 计算一次更新；若新数在 `(M,2M)` 内，答案直接变成新数；若新数至少 `2M`，枚举此前所有数和新最大值计算。总复杂度为 `O(n log A)`。",
            "primary_topic": "数论与同余",
        },
        "2113B": {
            "statement_brief": "给定一个 `w×h` 屋顶和不可旋转的 `a×b` 板材。两块板已经放好且不重叠，板材可以伸出屋顶边界，问不移动这两块板时能否把整个屋顶铺满。",
            "transformed_statement": "因为板材允许越界，问题不在边界，而在两块已放板材是否能同时落在某个按列或按行铺开的网格对齐方式里。",
            "key_observations": [
                "若两块板的左下角横坐标同余于 `a`，可以按列铺；若纵坐标同余于 `b`，可以按行铺。",
                "反过来，任意合法铺法看第一块板左下角附近的相邻格子，会被迫延伸成同列或同行的铺法。",
                "两块板同横坐标或同纵坐标的特殊情况，也会退化到对应的行列对齐条件。",
            ],
            "solution_brief": "关键观察：边界可以忽略，只检查两块固定板之间的网格对齐。若 `x1!=x2` 且 `(x2-x1)` 能被 `a` 整除，则按列补齐；若 `y1!=y2` 且 `(y2-y1)` 能被 `b` 整除，则按行补齐。两者都不满足时局部相邻板会产生无法对齐的缝隙，答案为 NO。",
            "primary_topic": "构造与贪心",
        },
        "2092D": {
            "statement_brief": "给一个只含 `L/I/T` 的字符串。一次操作可在相邻不同字符之间插入第三种字符，要求在不超过 `2n` 次操作内让三种字符数量相等，或判无解。",
            "transformed_statement": "每次按当前出现次数排序，优先把最少的字符插进去；若暂时没有可插位置，就用一个固定的四步小构造制造位置并降低不平衡度。",
            "key_observations": [
                "若原串所有字符都相同，则没有任何合法插入位置，必定无解；否则总能构造。",
                "设当前计数为 `cnt(a)<=cnt(b)<=cnt(c)`；若串中有 `bc` 或 `cb`，一插就能增加最少的 `a`。",
                "若没有这种相邻对，则一定能在含最多字符 `c` 和最少字符 `a` 的相邻对上，用四步构造制造一次有效推进。",
                "每次推进都会让 `2*cnt(c)-cnt(b)-cnt(a)` 下降，题解证明总操作数不超过 `2n`。",
            ],
            "solution_brief": "关键观察：不要试图直接构造最终串，而是持续消掉当前最大计数和最小计数的差。循环中重新排序三种字符计数，能插最少字符就插；否则在合适相邻对上套固定四步序列。计数相等时输出所有插入位置；若初始无合法相邻对则输出 -1。",
            "primary_topic": "构造与贪心",
        },
        "2092C": {
            "statement_brief": "给数组 `a`。一次操作可选一奇一偶两数，把某个正数减一并把另一数加一。问任意多次操作后数组最大值能达到多少。",
            "transformed_statement": "操作会保持奇数元素个数不变；如果同时存在奇偶数，就能把几乎全部总和集中到一个数上，只留下其它奇数各为 1。",
            "key_observations": [
                "若所有数同奇偶，则任意两数和都是偶数，无法操作，答案就是初始最大值。",
                "每次操作只会让一个奇数变偶数、一个偶数变奇数，所以奇数元素数量 `k` 不变。",
                "当奇偶都存在时，最终必须保留 `k` 个正奇数，因此最大值至多为 `S-k+1`。",
                "题解构造先把所有偶数并入某个奇数，再从其它奇数各拿出 1，剩余偶数继续并入主数，达到上界。",
            ],
            "solution_brief": "关键观察：唯一的不变量是奇数个数。统计总和 `S` 和奇数个数 `k`；若 `k=0` 或 `k=n`，没有操作空间，输出 `max(a)`。否则上界 `S-k+1` 可构造达到，直接输出它。",
            "primary_topic": "构造与贪心",
        },
        "2032E": {
            "statement_brief": "给一个奇数长度的环形数组。一次操作在某个位置及左右邻居上分别加 `2,1,1`，要求输出任意操作序列使所有元素相等，或判无解。",
            "transformed_statement": "先允许“负操作次数”在线性空间里配平；得到的操作次数整体加同一个常数后，每个数组元素都会增加同样的量，于是可把负数次数归一成非负。",
            "key_observations": [
                "奇数环上，同一奇偶间隔的一串操作可以只影响一个对称层和更内侧的层，不会破坏已经配平的外层。",
                "第一步从外向内把 `a_i` 与 `a_{n+1-i}` 配成相等，形成左右对称的“沟槽”。",
                "第二步从中心向外扩展平台，用奇数长度区间上的同奇偶操作串把相邻层拉平。",
                "最终若某些位置操作次数为负，给所有位置操作次数同时加上 `-min(v_i)`，只会给每个元素加同样的常数。",
            ],
            "solution_brief": "关键观察：把构造拆成“先做对称沟槽，再抬平成平台”。按题解两阶段维护操作次数差分：先处理每组对称端点的差值，在环上隔一个位置更新；再处理中心向外的平台差值。最后把操作次数整体平移到非负，并按次数输出对应下标。",
            "primary_topic": "构造与贪心",
        },
        "2021C2": {
            "statement_brief": "有 `n` 名成员按数组 `a` 排队，`m` 张幻灯片依次由队首讲；每讲完可把队首移到任意位置。给定并动态修改讲者序列 `b`，每次判断是否可能实现。",
            "transformed_statement": "按初始队列把成员重编号后，一个序列可行当且仅当各成员在 `b` 中的第一次出现位置按编号非降。",
            "key_observations": [
                "队首成员必须最先作为新成员出现；讲过一次后，他可以被提前安排到未来任意需要的位置。",
                "因此成员第一次变成“可等待成员”的顺序，必须和初始队列顺序一致。",
                "令 `first[x]` 为成员 `x` 在 `b` 中第一次出现的位置，不出现则为 `m+1`；可行条件就是 `first[1]<=first[2]<=...<=first[n]`。",
                "单点修改只会改变两个成员的出现位置集合，进而只影响 `first` 数组中相邻的少数比较。",
            ],
            "solution_brief": "关键观察：动态维护的不是整个队列，而是每个成员第一次出现的时间。为每个成员维护它在 `b` 中出现下标的有序集合，`first[x]` 取集合最小值或 `m+1`。再维护满足 `first[x]<=first[x+1]` 的相邻对数量；每次修改前后只更新旧值和新值附近的比较，数量等于 `n-1` 时输出可行，否则输出不可行。",
            "primary_topic": "数据结构",
        },
        "2258E": {
            "statement_brief": "给正整数数组。定义 `f(l,r)` 为没有整除子数组 LCM 的最小正整数，要求找出所有能作为某个子数组 `f(l,r)` 的正整数。",
            "transformed_statement": "固定候选 `x` 时，子数组里不能出现 `x` 的倍数；这些倍数把数组切成若干段，只需看某段内是否已经覆盖了所有让 `1..x-1` 整除 LCM 的必要因子。",
            "key_observations": [
                "若 `f(l,r)=x`，则所有小于 `x` 的数都要整除该段 LCM，而 `x` 不能整除该段 LCM。",
                "`x` 的倍数是障碍；合法区间一定落在两个相邻障碍之间。",
                "候选 `x` 不需要无限枚举，只需到超过 `n` 的最小质数幂附近，因为更大的最小缺失因子不可能被必要质数幂支撑。",
                "优化时遍历每个 `a_i` 的因子，更新这些因子的最近覆盖位置，用最小值数据结构判断当前障碍间是否全覆盖。",
            ],
            "solution_brief": "关键观察：把“LCM 缺的最小数”转成“障碍段内的因子覆盖”。枚举候选 x；遇到 `a_i` 是 x 的倍数时更新该候选的上一个障碍。对每个位置枚举 `a_i` 能覆盖的因子并维护最近出现位置，若所有小于 x 的必要因子最近位置都在上一个障碍之后，就说明某段能取到 `f=x`。",
            "primary_topic": "数论与同余",
        },
        "2258C": {
            "statement_brief": "交互题。隐藏图是一棵树；一次询问给 `u,v,d`，返回 `dist(u,v)>=d` 是否成立。要求在 `3n` 次询问内找出树的直径长度和一对直径端点。",
            "transformed_statement": "用阈值询问模拟“找最远点”：维护当前最大距离，只在某个点可能更远时继续询问精确距离。",
            "key_observations": [
                "固定起点时，若询问显示某个点距离达不到当前最优值加一，就可以直接跳过。",
                "若它可能更远，就从当前阈值继续递增询问，直到刚好确定这个点到起点的距离。",
                "从任意点找到一个最远点后，再以该最远点为起点重复一次，就能得到直径另一端。",
                "距离总增长次数最多 `n-1`，配合每个点一次过滤询问，整体询问数可压进 `3n`。",
            ],
            "solution_brief": "关键观察：阈值查询不必为每对点二分距离。先从 1 号点扫描所有点，维护当前最远端和距离；每个点先问能否超过当前距离，不能就跳过，能则递增阈值补出真实距离。得到一个直径端点后再扫描一遍，得到另一个端点和直径长度。",
            "primary_topic": "交互",
        },
        "2249E1": {
            "statement_brief": "定义无限 `k` 进制字符串，第 `i` 位是 `i` 的 k 进制数位和模 k。多次询问区间 `[l,r]` 中模式串 `t` 的出现次数。",
            "transformed_statement": "把长度 `k^i` 的前缀看成标准块；块会递归分成 k 个更小块，且每个子块只是整体字符加一的平移版本。",
            "key_observations": [
                "令 `B[i][j]` 表示长度 `k^i` 且所有字符整体加 `j` 的块，则 `B[i][j]=B[i-1][j]B[i-1][j+1]...B[i-1][j+k-1]`。",
                "每个块只需维护内部匹配数、长度不超过 `|t|-1` 的前缀和后缀；跨边界的新匹配只会出现在后缀加前缀里。",
                "当块长达到模式串长度级别后，边界串只和整体平移量有关，跨边界贡献可以预处理成 `k^2` 种转移。",
                "任意查询区间可按 k 进制分解成 `O(k log V)` 个标准块，再按顺序合并这些块的信息。",
            ],
            "solution_brief": "关键观察：这是自相似字符串上的区间模式匹配。对当前模式串先建 KMP；预处理各层标准块的内部出现次数和边界信息，较大层只保留平移编号并用预处理转移计算跨界匹配。查询时把 `[l,r]` 分解成若干标准块，像拼字符串一样合并节点，得到总出现次数。",
            "primary_topic": "字符串",
        },
        "2237F": {
            "statement_brief": "一次刷漆会选长度为 `m` 的区间并写入 `1..m`，后刷会覆盖先刷。给最终数组 `a`，求最少修改多少位置后它能由若干刷漆操作得到。",
            "transformed_statement": "先刻画合法数组的相邻关系：首位必须是 1，末位必须是 m；每对相邻值要么连续加一，要么在某个刷漆段边界处断开。",
            "key_observations": [
                "合法数组当且仅当 `a1=1`、`an=m`，且每对相邻值满足 `a_i=m` 或 `a_{i+1}=1` 或 `a_{i+1}=a_i+1`。",
                "必要性来自相邻位置若属于同一次刷漆就必须连续，否则较晚覆盖的一侧必须是区间端点。",
                "充分性可把连续属于同一刷漆操作的位置缩成段，再按是否含 1 决定把操作插到已有序列前还是后。",
                "求最少修改等价于保留最多原位置；保留点之间只要满足三类可转移关系即可。",
            ],
            "solution_brief": "关键观察：不要直接改数组，而是求最长可保留子序列。设 `dp[i]` 为最后保留位置为 i 时最多保留数；从 i 转到 j 的条件对应同一刷漆段、跨过右端点、跨过左端点三种情况。第一类用桶维护 `a_i-i`，后两类用前缀最大优化，最终答案为 `n-最多保留数`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2228B": {
            "statement_brief": "两人在环上追逃。Remilia 每秒可停或走一步，但全程最多走 `k` 次；Reimu 看完她的动作后也可停或走一步。双方最优，求几秒后追上。",
            "transformed_statement": "状态只需要看两人在环上的最短距离；Remilia 的每次移动最多把距离多拖一秒，Reimu 每秒把距离缩短一格。",
            "key_observations": [
                "当 `n<=3` 时，环太小，Reimu 总能一秒内追上。",
                "当 `n>=4` 时，若当前距离为 1，Remilia 仍能走到相邻空位把距离增加 1。",
                "Remilia 为了拖延，应尽量把所有可移动次数都用来增加距离。",
                "初始最短环距为 `min(|x1-x2|, n-|x1-x2|)`，答案就是这个距离加上 `k`。",
            ],
            "solution_brief": "关键观察：复杂策略博弈退化成距离变化。若 `n<=3` 直接输出 1；否则计算两点在环上的最短距离 d。Remilia 的每次有效移动贡献一秒拖延，Reimu 每秒只能追回一格，所以答案为 `d+k`。",
            "primary_topic": "博弈",
        },
        "2217C": {
            "statement_brief": "在 `n×m` 环形网格中从 `(1,1)` 出发，必须交替向下跳 `a` 和向右跳 `b`，问有限步内能否访问所有格子。",
            "transformed_statement": "把位置加上“下一步该往哪个方向”视为状态；两步一轮后的位移是 `(a,b)`，所以路径长度由两个模环上的周期决定。",
            "key_observations": [
                "要覆盖所有行和列，必须有 `gcd(n,a)=1` 且 `gcd(m,b)=1`。",
                "在上述条件下，完整两步循环回到同状态需要 `lcm(n,m)` 轮，所以最多访问 `2*lcm(n,m)` 个方向状态。",
                "若 `gcd(n,m)>=3`，格子数 `n*m` 已超过可访问状态数，必不可能覆盖。",
                "若 `gcd(n,m)=1` 或 2，题解分别用对称性和同余矛盾证明不会漏格，最终条件为 `gcd(n,m)<=2`。",
            ],
            "solution_brief": "关键观察：交替移动本质是模环上的单周期轨道。先检查 `gcd(n,a)` 和 `gcd(m,b)` 是否都为 1；否则行或列本身覆盖不全。再比较 `gcd(n,m)`：只有不超过 2 时轨道状态数足以覆盖且不会在同一格重复浪费方向状态，输出 YES，否则 NO。",
            "primary_topic": "数论与同余",
        },
        "2211C1": {
            "statement_brief": "给排列 `a`、含 `-1` 的数组 `b` 和窗口长度 `k`。要求补全 `b`，使每个长度 k 的窗口中，`a` 与 `b` 的多重集都相同。",
            "transformed_statement": "滑动窗口约束会固定两端：前 `n-k` 个位置和后 `n-k` 个位置必须与 `a` 相同，中间公共区间只需作为多重集匹配。",
            "key_observations": [
                "因为 `a` 是排列且每个元素至少出现在某个窗口中，补完后的 `b` 也必须是排列。",
                "`k=n` 时只检查 `b` 是否能补成无重复排列；`k=n-1` 时两端各一位被强制相等。",
                "推广后，所有长度 k 窗口的公共部分长度为 `max(2k-n,0)`，公共部分外的位置都会被某个窗口单独排除，因此必须逐位相等。",
                "若 `2k<n`，公共部分为空，直接要求 `a=b`；否则中间部分只需补成和 `a` 的中间部分同一个多重集。",
            ],
            "solution_brief": "关键观察：别逐个窗口比较，先找哪些位置被所有窗口共同包含。对两端非公共区间，`b_i` 若已给出就必须等于 `a_i`；对中间公共区间，统计 `a` 中这些数的需求，再用 `b` 已给值扣掉需求并检查重复或非法，剩余 `-1` 任意填缺失值即可。",
            "primary_topic": "构造与贪心",
        },
        "2229F": {
            "statement_brief": "给 n 个数和 k 个桶。可以任意重排数，然后依次把每个数加到当前最小桶里；最终分数是最大桶值，要求最大化这个分数。",
            "transformed_statement": "最大元素可以放到最后；在它之前的问题变成：能否把剩余数分成至少 k 组，每组和都达到某个下界 v。",
            "key_observations": [
                "题解证明最大元素放最后不劣，因为最后加入最大桶能把已构造的下界整体抬高。",
                "固定最后的最大数后，要最大化最后前所有桶的最小值。",
                "对候选 v，若剩余数能划出至少 k 个不交子集且每个子集和不少于 v，就能构造出桶最小值至少 v 的顺序。",
                "n<=18，子集 DP 可维护 `已完成组数、当前未满组剩余和`，检查一个 v。",
            ],
            "solution_brief": "关键观察：先把最大值拿掉并放到最后，答案是“剩余数能保证的最小桶值 + 最大值”。二分这个最小桶值 v；用 bitmask DP 扫所有子集，加入一个数后若当前组和达到 v 就完成一组并清空 leftover。若全集能完成至少 k 组，则 v 可行。",
            "primary_topic": "动态规划与状态设计",
        },
        "2219B1": {
            "statement_brief": "交互题。有长度 `2n+1` 的隐藏数组，除一个值出现三次外其它值都出现两次；一次询问返回给定位置集合中只出现一次的值的个数。要找出三次出现的位置。",
            "transformed_statement": "询问一个集合 S 和它的补集，可以判断三个特殊位置有多少个落在 S 中，从而做二分定位。",
            "key_observations": [
                "对 S 和补集 T 同时询问后，答案差异能暴露 S 是否含有恰好一个特殊位置。",
                "若两边答案相同，则 S 含特殊位置数为 0 或 3，可用 `|S|-query(S)` 的奇偶性区分。",
                "这样就能写一个判定函数：给定 S，回答 S 内特殊位置数量是 0、1、2 还是 3 中的哪类。",
                "找到一个特殊位置后，后续二分时忽略已找到的位置，重复三次即可。",
            ],
            "solution_brief": "关键观察：互补询问把“重复值计数”转成特殊三元组落点计数。用这个判定函数对下标区间做二分，先找任意一个特殊位置；再把它排除，继续二分找第二、第三个。简单版询问上限足够支撑三轮二分。",
            "primary_topic": "交互",
        },
        "2208E": {
            "statement_brief": "数组 P 若能表示为某个数组 A 中每个位置左侧最后一个更小元素的下标，则称 P 合法。给含 -1 的 X，统计替换后合法的数组数。",
            "transformed_statement": "合法性可用单调栈刻画：处理 i 时，`P_i` 必须还在栈里，然后弹到它成为栈顶，再把 i 入栈。",
            "key_observations": [
                "`P_i>=i` 必然非法，因为左侧下标不可能到达 i 或更右。",
                "若某个固定 `P_i` 已经被 earlier 位置弹出，就无法再作为 i 的左侧最后更小位置。",
                "等价禁用条件是不存在固定对 `(j,i)` 满足 `P_j < P_i < j < i`。",
                "固定值形成区间 `[P_i,i]`，按区间长度从小到大处理，可把一般情形化成 `-1` 或 `i-1` 的基础 DP。",
            ],
            "solution_brief": "关键观察：不要构造 A，而是数可能的单调栈历史。先检查所有固定值是否违反 `P_i<i` 和交叉禁用条件；若合法，把每个固定 `P_i` 看作区间约束，按短区间先处理。每段内部用栈大小 DP，`-1` 表示可弹任意层，固定为前驱表示不能弹，配合前缀和做到 O(n^2)。",
            "primary_topic": "动态规划与状态设计",
        },
        "2187A": {
            "statement_brief": "给数组 a。若只允许交换差值至少为 k 的两个元素仍能把数组排好，则 k 可行；求最大的可行 k，若数组本来有序则输出 -1。",
            "transformed_statement": "真正需要移动的元素，只要它和全局最小值或全局最大值的差至少 k，就能借助这两个极值间接完成任意交换。",
            "key_observations": [
                "若数组已经有序，不做操作即可满足任意 k，按题意输出 -1。",
                "若 `max-min<k`，没有任何交换可做，k 不可行。",
                "对一个位置 i，若 `a_i` 已经在排序后正确位置，就不用动。",
                "对必须移动的值 x，若它到全局最小和全局最大距离都小于 k，它永远无法参与交换；否则可用极值作为中转。",
            ],
            "solution_brief": "关键观察：可交换性由全局极值提供“中转站”。排序得到目标数组 b；只检查 `a_i!=b_i` 的位置。答案可直接取这些值的 `max(x-min, max-x)` 的最小值；因为 k 不能超过任何必动值可连接到极值的能力。若原数组已排序输出 -1。",
            "primary_topic": "构造与贪心",
        },
        "2180C": {
            "statement_brief": "构造 k 个 `[0,n]` 内整数，使它们的异或为 n，并最大化这些数的总和。",
            "transformed_statement": "从高位到低位贪心：每一位的 1 的个数奇偶由 n 的该位决定，而总和要求尽量让更多数在高位取 1。",
            "key_observations": [
                "高位多放一个 1 的收益超过所有低位调整收益，所以应逐位贪心。",
                "维护 tight 集合表示当前前缀仍等于 n，loose 集合表示已经小于 n。",
                "n 当前位为 1 时，需要奇数个 1；尽量放最多的奇数个，若 k 偶数就让一个 tight 数在此位取 0 并变 loose。",
                "n 当前位为 0 时，tight 数不能放 1，只能在 loose 数里放尽量多的偶数个 1。",
            ],
            "solution_brief": "关键观察：异或只限制每位取 1 的奇偶，`a_i<=n` 由 tight/loose 前缀控制。按位从高到低处理；若 n 位为 1，放 `k` 或 `k-1` 个 1；若 n 位为 0，只在 loose 中放偶数个 1。这样每一位都局部最优，并保持后续可行。",
            "primary_topic": "构造与贪心",
        },
        "2164D": {
            "statement_brief": "每次可把字符串中每个位置变成原位置字符或左邻字符，要求用不超过 kmax 次把 s 变成 t，并输出每一步字符串。",
            "transformed_statement": "第 k 步的每个位置 j 实际来自初始串某个位置 `p_j`；p 必须非降，且 `p_j` 在 `[j-k,j]` 内。",
            "key_observations": [
                "字符只能向右复制，经过 k 步后位置 j 的来源不可能早于 `j-k`，也不可能晚于 j。",
                "所有来源下标 p_j 必须非降，否则会违反复制传播的顺序。",
                "若存在满足 `s[p_j]=t_j` 的合法 p，就一定能通过归纳构造出 k 步过程。",
                "固定 k 时，从左到右给每个 j 选最小可行 p_j，就能贪心判断是否存在合法 p。",
            ],
            "solution_brief": "关键观察：先判定最终来源数组 p，而不是直接搜操作序列。枚举 k 从 0 到 kmax，用贪心检查是否能为每个 t_j 选择一个非降来源 `p_j in [j-k,j]` 且字符匹配。找到最小 k 后，按题解的归纳方式逐轮生成字符串，并把 p 中小于当前位置的来源整体右移一格。",
            "primary_topic": "字符串",
        },
        "2161E": {
            "statement_brief": "给含问号的二进制串和奇数 k，要求统计填法，使每个长度 k 子串中最左字符出现次数严格多于另一种字符。",
            "transformed_statement": "先假设第一个长度 k 子串中 1 占多数；0 占多数的情况对称。之后所有窗口会被“第一次多数差为 1 的位置”决定。",
            "key_observations": [
                "长度 k 为奇数，每个窗口多数一定唯一。",
                "若 `d[1,k]>0`，必须有 `s_1=1`；若多数差大于 1，向右滑动会强迫 `s_2` 也为 1。",
                "存在第一个位置 l 使该窗口多数差恰为 1 时，前缀 `1..l` 全被确定为 1，后面按周期 k 复制。",
                "若一直没有差为 1 的窗口，则前 `n-k+1` 位全固定为 1，最后 k-1 位只需总平衡为正。",
            ],
            "solution_brief": "关键观察：所有合法串只有两大结构。分别枚举首窗口多数为 1 和为 0；对第一类，倒序枚举第一次达到差 1 的 l，维护从 l 后开始的 k 周期同余类是否与原模式冲突，并用组合数统计中间自由位；第二类直接统计后缀填法使平衡仍为正。两种颜色对称相加。",
            "primary_topic": "组合计数与概率",
        },
        "2161B": {
            "statement_brief": "给 n×n 黑白网格，只能把白格涂黑。目标是黑格四连通且不存在任意横向或纵向连续三个黑格，问是否可行。",
            "transformed_statement": "满足条件的连通形状只有两类：一个 2×2 方块，或沿两条相邻对角线走的锯齿形。",
            "key_observations": [
                "若有连续三黑限制，连通区域不能变厚，只能保持宽度 2 的方块或锯齿通道。",
                "2×2 情况只需检查所有已有黑格是否落在同一个 2×2 框内。",
                "锯齿形等价于所有黑格落在某一种对角线方向的两条相邻对角线上。",
                "两种对角线方向分别对应 `x+y` 和 `x-y`，检查已有黑格这些值的最大差是否不超过 1。",
            ],
            "solution_brief": "关键观察：不是搜索涂哪些格，而是判已有黑格能否嵌进允许形状。收集所有黑格坐标；若空集可以直接涂一个格。否则检查三种条件：坐标范围是否可放进某个 2×2，`x+y` 范围是否不超过 1，或 `x-y` 范围是否不超过 1。任一成立则 YES。",
            "primary_topic": "构造与贪心",
        },
        "2157D": {
            "statement_brief": "有若干报价 a_i。你可对每个报价选择忽略、赌最终排名 p 不超过 a_i、或赌 p 不小于 a_i；已知 `l<=p<=r`，最大化最坏收益。",
            "transformed_statement": "固定策略后收益关于 p 是一条直线，所以最坏点只会在 l 或 r；排序后最优策略是前缀押一侧、后缀押另一侧，最多跳过一个报价。",
            "key_observations": [
                "线性函数在区间上的最小值发生在端点，因此只测 p=l 和 p=r。",
                "排序后若较小报价被忽略而较大报价押同一侧，交换选择不会更差。",
                "可整理成前缀押 `p>=a_i`，后缀押 `p<=a_i`。",
                "若有两个报价都忽略，把较小的押左、较大的押右不会降低最坏收益，所以最多忽略一个。",
            ],
            "solution_brief": "关键观察：把策略空间压到 O(n)。先排序并做前缀和；枚举分界点以及可能被忽略的那个报价，O(1) 计算该策略在 p=l 和 p=r 时的收益，取二者较小作为保证值。所有候选取最大即可。",
            "primary_topic": "构造与贪心",
        },
        "2153B": {
            "statement_brief": "给 x、y、z，问是否存在非负整数 a、b、c，使 `a&b=x`、`b&c=y`、`a&c=z`。",
            "transformed_statement": "按位互不影响。更直接地，候选可取 `a=x|z`、`b=x|y`、`c=y|z`，再验证三条 AND 等式。",
            "key_observations": [
                "AND 的每一位独立，所以可以逐位枚举 a、b、c 的三个位。",
                "若某位必须在 `a&b` 和 `a&c` 中为 1，那么 a 该位必须为 1；其它变量同理。",
                "因此最小自然候选是 `a=x|z`、`b=x|y`、`c=y|z`。",
                "这个候选若验证失败，则任何方案都无法满足对应位的所有约束。",
            ],
            "solution_brief": "关键观察：三条 AND 约束直接决定每个变量至少需要哪些 1 位。构造 `a=x|z`、`b=x|y`、`c=y|z`，然后检查 `(a&b)==x`、`(b&c)==y`、`(a&c)==z`。全部成立输出 YES，否则 NO。",
            "primary_topic": "基础实现与模拟",
        },
        "2150A": {
            "statement_brief": "有一条很长的黑白格带和命令串。第 i 个人从 1 出发执行前 i 个命令，最后把停下的格子染黑；求最终所有黑格。",
            "transformed_statement": "第 i 个人和第 i-1 个人的路径几乎相同；新染黑的格子只可能影响最后一两步，不会影响更早前缀。",
            "key_observations": [
                "第 i 个人执行的是第 i-1 个人命令串再多一个命令。",
                "第 i-1 个人新染黑的格子可能改变第 i 个人倒数第一步的跳转结果。",
                "但它离前 i-2 步访问过的位置太远，不会改变这些更早位置。",
                "因此每轮只需从上轮前缀位置出发，朴素模拟最后两条命令。",
            ],
            "solution_brief": "关键观察：不用每个 i 从头跑命令。维护相邻两轮共享的前缀终点；新增一轮时，只重新模拟最后两步，并用集合/并查集维护“下一个白格”查询。每轮 O(log n) 或近似 O(1)，最后输出初始黑格和所有新增黑格。",
            "primary_topic": "数据结构",
        },
        "2122G": {
            "statement_brief": "对所有 n 点带标号树，求停车时间区间方案数之和，并按叶子数 k 分类。",
            "transformed_statement": "单棵树的方案数可化为 `(2n)! / (2^n * product(subtree_size))`；因此全局只需求所有带标号树上 `1/product(subtree_size)` 的总和。",
            "key_observations": [
                "单棵树合法当且仅当任一点的停车区间内部不包含其子树中其它车的进入或离开端点。",
                "化简后，单棵树贡献只依赖所有子树大小乘积。",
                "树的拓扑序数量为 `n! / product(subtree_size)`，于是问题转成统计所有带标号树的拓扑序数量。",
                "固定一个拓扑序后，父亲必须在儿子之前；按叶子数得到递推 `f(n,k)=f(n-1,k-1)(n-k)+f(n-1,k)k`，即欧拉数。",
            ],
            "solution_brief": "关键观察：把停车区间计数转成树拓扑序计数。利用单树公式和拓扑序公式，所求和等价于欧拉数 `A(n-1,k-1)` 乘上统一系数。最终答案为 `A(n-1,k-1)*(2n)!/(n*2^n)`，欧拉数用容斥或快速公式计算。",
            "primary_topic": "组合计数与概率",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2128D": {
            "statement_brief": "给一个满足 `max(p_i,p_{i+1})>p_{i+2}` 的排列。要求对所有子数组，求最长下降子序列长度之和。",
            "transformed_statement": "把题目先看成：在这种特殊排列里，子数组的 LDS 长度等于子数组长度减去其中上升相邻对的数量。",
            "key_observations": [
                "所有下降位置 `i`（满足 `p_i>p_{i+1}`）选出的元素本身能组成一个下降子序列。",
                "每个上升相邻对 `(i,i+1)` 中，任意下降子序列最多选一个，因为这两个值顺序和值大小都不允许同时进入。",
                "题目给出的三元条件保证不同上升相邻对互不重叠，并且下降位置集合已经达到这个上界。",
                "所以统计所有子数组时，只需从所有子数组长度总和中扣掉每个上升相邻对被包含的次数。",
            ],
            "solution_brief": "关键观察：特殊条件把 LIS/LDS 问题压成相邻贡献。总子数组长度和为 `n(n+1)(n+2)/6`；对每个 `p_i<p_{i+1}`，所有包含这对相邻元素的子数组都会让 LDS 少 1，贡献次数是 `i*(n-i)`（按 1-index）。总和减去这些贡献即答案。",
            "primary_topic": "组合计数与概率",
        },
        "2120B": {
            "statement_brief": "方形台球桌四角有袋，若干球从整数坐标以 45 度方向同时发射并弹性碰撞。问最终会进袋的球数。",
            "transformed_statement": "把题目先看成：球与球碰撞只是在交换速度方向，因此只影响“哪颗球”走哪条轨迹，不影响“多少条轨迹”进袋。",
            "key_observations": [
                "单个球在无其它球时，只有沿两条对角线并朝对应角落运动时才会进袋。",
                "撞墙后的轨迹是周期性的；不在可入袋对角线上的轨迹会一直弹来弹去。",
                "两个完全相同质量的球弹性碰撞，等价于它们交换方向。",
                "因此总进袋数量不受球间碰撞影响，只数初始位置和方向对应的入袋轨迹。",
            ],
            "solution_brief": "关键观察：不要模拟运动和碰撞。若 `dx==dy`，球沿 `x-y` 不变的对角线运动，只有 `x==y` 会进袋；若 `dx!=dy`，沿另一组对角线运动，只有 `x+y==s` 会进袋。逐球判断并计数即可。",
            "primary_topic": "几何",
        },
        "2108A": {
            "statement_brief": "对长度 n 的排列 p，定义 `f(p)=sum |p_i-i|`。问所有排列能产生多少种不同的 f 值。",
            "transformed_statement": "把题目先看成：从恒等排列逐步走到反序排列时，f 可以每次增加 2，并覆盖全部可能偶数。",
            "key_observations": [
                "任意交换只会让 `sum |p_i-i|` 的奇偶性保持为偶数。",
                "最大值由反序排列达到，等于 `floor(n^2/2)`。",
                "把 n 一步步移到最前，再把 n-1 移到第二位，依次进行，每一步 f 都恰好增加 2。",
                "于是从 0 到最大值之间的所有偶数都能取到，且没有其它奇数值。",
            ],
            "solution_brief": "关键观察：不是枚举排列，而是证明可取值正好是一段偶数。可取值数量为 `floor(floor(n^2/2)/2)+1 = floor(n^2/4)+1`；实现时可写成 `n/2 * ((n+1)/2) + 1`。",
            "primary_topic": "组合计数与概率",
        },
        "2103E": {
            "statement_brief": "数组元素都在 `[0,k]`。一次操作只能选和为 k 的两个位置，在二者之间转移若干值。要求在 `3n` 次内把数组变成非降，或判无解。",
            "transformed_statement": "把题目先看成：只要存在一对和为 k 的位置，它们就能作为“缓冲器”交换其它任意两个位置的值。",
            "key_observations": [
                "若数组未排序且不存在任意一对和为 k，则根本无法执行任何有用操作，必定无解。",
                "固定一对缓冲位置 A、B 且 `a_A+a_B=k`，三次操作可以交换任意两个其它位置 C、D，同时保持 A、B 的和仍为 k。",
                "为了最后不被缓冲器本身卡住，可以先把这对缓冲器搬到数组首尾。",
                "首尾作为缓冲器后，中间位置可按值排序，最后把首尾设置为 0 和 k，整个数组自然非降。",
            ],
            "solution_brief": "关键观察：可行性只有“已排序”或“存在互补对”两种。若已非降输出 0；否则找一对和为 k 的位置。用题解给出的两步把缓冲对移动到 1 和 n，再用三步交换过程把中间 `2..n-1` 按值排序，最后把首尾改成 `0,k`，操作数满足 `3n`。",
            "primary_topic": "构造与贪心",
        },
        "2085C": {
            "statement_brief": "给正整数 x、y，要求找 `0<=k<=1e18`，使 `(x+k)+(y+k)=(x+k) xor (y+k)`，无解输出 -1。",
            "transformed_statement": "把题目先看成：加法等于异或当且仅当两个数二进制没有共同的 1 位。",
            "key_observations": [
                "`a+b=a xor b` 等价于加法过程中没有进位，也就是 `(a&b)=0`。",
                "若 `x==y`，加同一个 k 后两数仍相等且为正，不可能按位与为 0。",
                "若 `x!=y`，把较大的那个数补到足够大的 2 的幂 P。",
                "另一个数加同样的 k 后仍小于 P，因此不会与 P 的唯一高位重合。",
            ],
            "solution_brief": "关键观察：构造一个 2 的幂即可。若 `x==y` 输出 -1；否则取足够大的 `P=2^48`，令 `k=P-max(x,y)`。较大数变成 P，较小数仍小于 P，二者按位与为 0，所以公式成立。",
            "primary_topic": "构造与贪心",
        },
        "2061C": {
            "statement_brief": "n 个人排队，每人声称左边骗子数量；诚实者说真话，骗子可乱说且骗子不能相邻。问合法身份配置数。",
            "transformed_statement": "把题目先看成：只维护“当前第 i 个人诚实”的方案数；第 i 个人是骗子的方案会在答案中由前一个诚实状态补回来。",
            "key_observations": [
                "如果第 i 个人诚实，他左边骗子数量必须等于 `a_i`。",
                "若第 i-1 个人诚实，则第 i 个人也诚实时要求 `a_i=a_{i-1}`。",
                "若第 i-1 个人是骗子，则第 i-2 个人必须诚实，此时第 i 个人左边骗子数应为 `a_{i-2}+1`。",
                "因此 `dp_i` 只依赖 `dp_{i-1}` 和 `dp_{i-2}` 两种来源。",
            ],
            "solution_brief": "关键观察：不需要记录骗子状态。令 `dp_i` 为前 i 人合法且第 i 人诚实的方案数；若 `a_i=a_{i-1}` 加 `dp_{i-1}`，若 `a_i=a_{i-2}+1` 加 `dp_{i-2}`。最后答案是第 n 人诚实或第 n 人为骗子两类，即 `dp_n+dp_{n-1}`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2057A": {
            "statement_brief": "把 `0..n*m-1` 填入 n 行 m 列表格，最大化所有行 MEX 与所有列 MEX 的总和，只需输出最大值。",
            "transformed_statement": "把题目先看成：MEX 贡献几乎全由 0 和 1 决定；0 只会同时帮助一行一列，后续连续小数只能沿其中一个方向继续堆。",
            "key_observations": [
                "0 只出现在一个格子里，因此只有它所在的一行和一列的 MEX 可能大于 0。",
                "若 1 存在，它最多让含 0 的那一行或那一列继续增长，另一个方向最多只贡献 1。",
                "所以总贡献上界是较长维度上的连续小数长度，再加另一个方向的 1。",
                "把 `0..max(n,m)-1` 放在一整行或一整列即可达到这个上界。",
            ],
            "solution_brief": "关键观察：答案不是排表，而是上界可达。若 `n>m`，把 `0..n-1` 放在同一列；否则放在同一行。最大总 MEX 为 `max(n,m)+1`。",
            "primary_topic": "构造与贪心",
        },
        "2034E": {
            "statement_brief": "要求构造 k 个互不相同的 n 排列，使每个位置上 k 个数的和都相等；若不可能则输出 No。",
            "transformed_statement": "把题目先看成：互补排列成对出现时，每一列贡献恒为 `n+1`；奇数 k 需要额外处理 3 个排列的基底。",
            "key_observations": [
                "所有列总和平均后，每列必须等于 `(n+1)k/2`，因此某些奇偶组合天然无解。",
                "偶数 k 时，每个排列 `p` 与互补排列 `n+1-p_i` 配对，任意列和都是 `n+1`。",
                "奇数 k 不能只靠互补对，需要先构造 `k=3` 且 n 为奇数的一组三排列基底。",
                "`k=1` 除 `n=1` 外无解；当可用排列总数不足 k 或只差一个排列时也要判无解。",
            ],
            "solution_brief": "关键观察：构造单位是“互补对”，不是单个排列。先处理无解条件；若 k 为奇数，输出题解给出的 3 个排列基底并令 `k-=3`。剩余 k 为偶数时，按字典序枚举排列，若它和互补排列都未被用过，就成对加入，直到够 k 个。",
            "primary_topic": "构造与贪心",
        },
        "2032B": {
            "statement_brief": "给奇数 n 和 k，要把数组 `1..n` 分成奇数个奇长连续段，使这些段中位数的中位数等于 k。",
            "transformed_statement": "把题目先看成：除端点外，总能用 3 段让中间段的中位数正好是 k。",
            "key_observations": [
                "`n=1` 时只有 `[1]` 这一种平凡方案。",
                "当 `n>1` 且 `k=1` 或 `k=n` 时，任何奇长连续段的中位数都无法让最终中位数成为端点值。",
                "其它 k 用三段即可：前缀、中间含 k 的短段、后缀。",
                "为了让三段长度都为奇数，k 为偶数时中间段取 `[k,k]`，k 为奇数时取 `[k-1,k+1]`。",
            ],
            "solution_brief": "关键观察：目标不是复杂划分，只要让三段的中间那个中位数为 k。特判 `n=1`；若 `k` 是端点输出 -1。否则输出 3 段起点：k 为偶数用中段长度 1，k 为奇数用中段长度 3，保证左右两段长度也为奇数。",
            "primary_topic": "构造与贪心",
        },
        "2019B": {
            "statement_brief": "数轴上有 n 个递增整数点，画出所有两点之间的闭区间。多次询问有多少整数坐标点恰好被 k 条区间覆盖。",
            "transformed_statement": "把题目先看成：覆盖数在每个给定点处和每个相邻点间的空隙处都是固定公式，预处理进哈希表即可。",
            "key_observations": [
                "若整数点 p 位于 `x_i` 和 `x_{i+1}` 之间，则左端可选前 i 个点、右端可选后 n-i 个点，覆盖数为 `i(n-i)`。",
                "这样的空隙整数点数量是 `x_{i+1}-x_i-1`。",
                "若 p 正好是 `x_i`，左端可选 `1..i`、右端可选 `i..n`，但不存在 `[x_i,x_i]` 这条区间，所以覆盖数为 `i(n-i+1)-1`。",
                "不同位置只需按覆盖数汇总数量，询问直接查表。",
            ],
            "solution_brief": "关键观察：不要逐区间加覆盖。遍历每个原点 `x_i`，把 `i(n-i+1)-1` 的计数加一；遍历每个相邻空隙，把 `i(n-i)` 的计数加上空隙长度。每个询问 k 输出表中对应数量。",
            "primary_topic": "组合计数与概率",
        },
        "2005E1": {
            "statement_brief": "两人轮流按数组 a 的顺序，在矩阵 b 中选择等于当前目标值的格子；下一步只能在右下子矩阵中继续。不能行动者输，问先手是否必胜。",
            "transformed_statement": "把题目先看成：每个目标值对应一批可选格子；从后往前判断某格是否为必胜选择。",
            "key_observations": [
                "若当前选 `(r,c)` 后，右下子矩阵里存在下一步的必胜格子，对手会走过去，当前选择就是坏的。",
                "反过来，若右下子矩阵中没有下一步必胜格子，则当前玩家选 `(r,c)` 后能保证获胜。",
                "因此可从数组 a 的末尾向前做 minimax。",
                "每一层只需支持查询某个右下子矩阵里是否存在下一层必胜格，简单版可用二维后缀和直接维护。",
            ],
            "solution_brief": "关键观察：博弈状态不是整张棋盘路径，而是“当前目标值的每个格子是否必胜”。从最后一个目标值倒推到第一个；对所有值等于 `a_i` 的格子，查询其右下方是否有 `a_{i+1}` 层的必胜格。没有则标为必胜。最后若存在第一层必胜格则先手赢，否则后手赢。",
            "primary_topic": "博弈",
        },
        "2258B1": {
            "statement_brief": "简单版只有一次切割操作。给若干胡萝卜长度，选择一个 x 并切所有选中且长度大于 x 的胡萝卜，问最多能卖多少根等长胡萝卜。",
            "transformed_statement": "把题目先看成：固定目标长度 x 后，每根长度至少 x 的胡萝卜都能贡献一根 x；长度正好 2x 的会额外贡献第二根 x。",
            "key_observations": [
                "一次操作中选择长度大于 x 的胡萝卜并切成 x 和 `l-x`，所以目标成品长度自然枚举为 x。",
                "所有 `l>=x` 的胡萝卜至少可以保留或切出一根长度 x。",
                "只有当 `l=2x` 时，切出来的两段都等于 x，会多贡献一根。",
                "因此固定 x 的答案是 `count(l>=x)+count(l=2x)`。",
            ],
            "solution_brief": "关键观察：枚举目标长度即可。预处理长度频率和后缀数量；对每个可能的 x，计算 `长度>=x` 的数量，再加上 `长度=2x` 的数量，取最大值。",
            "primary_topic": "基础实现与模拟",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2249D": {
            "statement_brief": "给 n 和 x，构造一个 `n*n` 矩阵，要求每行每列都是 `0..n-1` 的排列，且每个相邻 `2*2` 子矩阵四个数异或为 x；无解输出 -1。",
            "transformed_statement": "把题目先看成：相邻两行的逐列异或差必须按列奇偶在 `h` 和 `h xor x` 间交替，因此需要很多能保持集合 `0..n-1` 不变的异或平移。",
            "key_observations": [
                "设 `S={0..n-1}`，若某个 h 满足 `S xor h = S`，这样的 h 必须属于 `0..lowbit(n)-1`。",
                "相邻行有至少 `ceil(n/2)` 个同奇偶列，所以需要至少这么多不同的稳定平移；这迫使 n 是 2 的幂。",
                "`x=0` 时直接用 `A[i][j]=i xor j`，行列都天然是排列。",
                "`x>0` 时把值按 `y <-> y xor x` 配对，分成偶位集合 E 和奇位集合 O，再用奇偶项额外异或 x 保证每个 `2*2` 的总异或为 x。",
            ],
            "solution_brief": "关键观察：先判 n 是否为 2 的幂，且 `n=2,x>0` 无解。可行时，`x=0` 输出 `i xor j`；否则把 `0..n-1` 按 `xor x` 成对分组，选一半 pair 放到奇位集合 O，另一半放到偶位集合 E，构造排列 p 后输出 `p_i xor p_j`，仅当 i、j 都为奇时再异或 x。",
            "primary_topic": "构造与贪心",
        },
        "2245A": {
            "statement_brief": "一排小猪朝左或朝右；若一头小猪参与至少 k 对“左边朝右、右边朝左”的配对，则它安全。可翻转若干方向，求让所有小猪安全的最少翻转数或判无解。",
            "transformed_statement": "把题目先看成：最左 k 个位置必须全朝右，最右 k 个位置必须全朝左，中间位置无需强制。",
            "key_observations": [
                "前 k 个位置若有朝左的小猪，它左边数量不足 k，不可能参与 k 个配对。",
                "对称地，后 k 个位置若有朝右的小猪，它右边数量不足 k，也不可能安全。",
                "若 `2k>n`，这两个强制区域重叠且方向要求冲突，必定无解。",
                "若不重叠，前缀 R 和后缀 L 互相提供 k 个配对，中间任意朝向也能和某一侧形成 k 个配对。",
            ],
            "solution_brief": "关键观察：只改两端。若 `2k>n` 输出 -1；否则统计前 k 个位置中不是 R 的数量、后 k 个位置中不是 L 的数量，二者之和就是最少翻转数，中间完全不用动。",
            "primary_topic": "构造与贪心",
        },
        "2209C": {
            "statement_brief": "交互题。隐藏数组长 `2n`，其中 `1..n` 各出现一次，其余都是 0；一次询问两个位置是否相等，要求在 `n+1` 次询问内找任意一个 0。",
            "transformed_statement": "把题目先看成：由于正数互不相同，询问返回相等当且仅当两个位置都是 0。",
            "key_observations": [
                "按 `(3,4),(5,6),...,(2n-1,2n)` 查询所有偶奇对，若返回 1 就已找到 0。",
                "若这些查询全返回 0，则每个被查 pair 至多一个 0。",
                "再询问 `(1,3)` 和 `(1,4)`；若任一返回 1，也找到 0。",
                "如果仍全为 0，用鸽巢分析可排除 `a_1=0` 或 `a_1,a_2` 都非 0，剩下只能是 `a_2=0`；这就是省掉 `(1,2)` 的关键。",
            ],
            "solution_brief": "关键观察：正数值本身无用，只需要找一对相等的 0。先跳过 `(1,2)`，查询后面 n-1 个相邻 pair；有相等就输出其中一个。否则查询 `(1,3)`、`(1,4)`，若也没有相等，根据零的总数和每个 pair 至多一个零可推出 2 号位必为 0。",
            "primary_topic": "交互",
        },
        "2208A": {
            "statement_brief": "给 `n*n` 个糖果颜色，可任意重排成 n 行 n 列。问能否让每一行、每一列都不是单色。",
            "transformed_statement": "把题目先看成：唯一障碍是某一种颜色太多，多到无法给每行至少塞一个其它颜色。",
            "key_observations": [
                "若最多颜色出现次数超过 `n^2-n`，其它颜色少于 n 个，必有一行全是这种颜色。",
                "这个条件同时足够：先把最多颜色放满主对角线，保证每行每列都有它。",
                "再把 n 个非最多颜色放到循环偏移对角线上，保证每行每列也都有其它颜色。",
                "剩余糖果任意填，不会破坏“每行每列至少两种颜色”。",
            ],
            "solution_brief": "关键观察：不需要真的输出重排，只判最大频率。统计所有颜色出现次数，若最大值 `mx <= n*(n-1)` 输出 YES，否则输出 NO。",
            "primary_topic": "构造与贪心",
        },
        "2196C2": {
            "statement_brief": "交互题。隐藏图是 DAG，可询问所有路径按字典序排序后的第 k 条路径；困难版要求用不超过 `n+m` 次询问恢复所有边。",
            "transformed_statement": "把题目先看成：按字典序连续观察路径，路径每次要么向后多一个顶点，要么弹掉一段后缀再接新分支。",
            "key_observations": [
                "若新路径只是比上一条多一个顶点，就直接学到一条新边。",
                "若新路径弹掉后缀，说明这些后缀顶点开头的路径块已经完整走完，可以计算它们各自的路径数量 `C_v`。",
                "以后再次到达某个顶点时，可以一次跳过它开头的 `C_v` 条路径，而不是一条条询问。",
                "这样每次有效询问要么发现一条边，要么跳到下一个尚未处理的连通部分，总次数正好受 `n+m` 控制。",
            ],
            "solution_brief": "关键观察：困难版不是二分第 k 条路径，而是顺序扫描加跳块。维护当前询问到的路径和每个顶点开头的路径数；比较相邻回答的最长公共前缀，新增顶点给出边，消失的后缀用于结算 `C_v`。遇到已知 `C_v` 的顶点时直接把 k 加上这块大小，直到所有路径块扫完。",
            "primary_topic": "交互",
        },
        "2187G": {
            "statement_brief": "给出一系列笛卡尔树父边集合的并集矩阵。原始排列 q 每轮会把当前最小值加 n；要求还原任意一个能产生该并集的排列 q。",
            "transformed_statement": "把题目先看成：可以逐步确定当前最大值的位置；若已知值 n 在位置 v，那么值 n-1 只能在 v 的极端孩子之一。",
            "key_observations": [
                "把 q 的所有值整体按模 n 旋转不影响答案，因此可从某个位置开始假设它是当前最大值。",
                "若值 n 在位置 v，则 `n-1` 不可能夹在 v 的孩子最小下标和最大下标之间，只可能是这两个极端孩子之一。",
                "笛卡尔树中，一个点到父亲的边不会跨过更大的位置 v；这个“是否跨过 v”的信息能区分左右两个候选。",
                "于是从最大值往下，每一步只在两个候选中选一个，直到填完整个排列。",
            ],
            "solution_brief": "关键观察：还原排列不用搜索。预处理每个点作为父亲的最小/最大孩子、每个点可能父亲的最小/最大位置；从某个起点赋值 n 开始，若所有极端孩子在 v 左侧就选最左，若都在右侧就选最右，否则用候选点是否存在跨过 v 的父边判断哪个是 n-1。反复下降填出 q。",
            "primary_topic": "树结构",
        },
        "2174D": {
            "statement_brief": "给无向带权图，要求选出恰好 `n-1` 条边，使它们不构成一棵树，并让权值和最小；若不存在输出 -1。",
            "transformed_statement": "把题目先看成：先取最轻的 `n-1` 条边。如果它们已经不是树，答案就是它们；否则它们形成一棵树 T，只需研究如何用更重的边替换。",
            "key_observations": [
                "若最轻的 `n-1` 条边不连通或成环，它们就是最优，因为任何其它选择都不可能更轻。",
                "否则设这棵树权和为 S；加入一条非树边 e 会形成基本环，要让选出的 `n-1` 条边不是树，必须删掉 T 中不在该环上的一条边。",
                "固定 e 时，最优删除的是“e 两端路径之外”的最大树边，代价为 `S+w(e)-mx_out_path`。",
                "若最优需要换两条以上边，题解给出下界 `S-w_{n-1}-w_{n-2}+w_n+w_{n+1}`，并证明这个下界可达。",
            ],
            "solution_brief": "关键观察：围绕最轻生成树 T 做一次或两次替换即可。先排序取前 `n-1` 条并查集判树；若不是树直接输出其权和。若是树，枚举后续边，用 HLD 或树上预处理查询路径外最大边，更新单边替换答案；再和“两条替换”的闭式候选取最小。",
            "primary_topic": "图论与网络流",
        },
        "2157C": {
            "statement_brief": "给若干区间约束：类型 1 要求区间最小值为 k，类型 2 要求区间 MEX 为 k。保证有解，要求构造任意数组。",
            "transformed_statement": "把题目先看成：每个位置只按它是否被最小值约束、是否被 MEX 约束分类。",
            "key_observations": [
                "被最小值约束覆盖的位置必须 `>=k`，为了满足最小值，最好直接放 k。",
                "被 MEX 约束覆盖的位置必须 `!=k`，并且需要尽快提供 `0..k-1`。",
                "同时被两类约束覆盖的位置对两边都没帮助，只需放一个 `k+1` 之类的安全值。",
                "只被 MEX 约束覆盖的位置按顺序填 `0,1,...,k-1` 循环；题目保证每个 MEX 区间能收齐这 k 种值。",
            ],
            "solution_brief": "关键观察：不用逐条构造区间，只给位置染四类。先标记每个位置是否属于 min 约束和 MEX 约束：两者都无关随便填；只在 min 中填 k；两者都有填 `k+1`；只在 MEX 中按计数器填 `cnt mod k`。这样所有 min 区间有 k，所有 MEX 区间缺 k 且含 `0..k-1`。",
            "primary_topic": "构造与贪心",
        },
        "2154F2": {
            "statement_brief": "给一个含 `-1` 的长度 n 排列，问有多少种补全方式能成为有序排列 `1..n` 的 riffle shuffle；困难版 `n<=1e6`。",
            "transformed_statement": "把题目先看成：一个合法洗牌可由某个切分点 k 把值分成左、右两侧；已知值若 `p_i<i` 必属左侧，若 `p_i>i` 必属右侧。",
            "key_observations": [
                "任何 riffle shuffle 都呈现三段结构：前缀固定点、中间全非固定点、后缀固定点。",
                "若已知值中存在非固定点，它会决定中间区域左右侧的归属，进而把多数未知段变成带边界类型的 gap 计数。",
                "若所有已知值都在原位，则每段连续 `-1` 可以按全未知公式 `2^len-len-1` 计数，最后补上完全有序方案。",
                "困难版对跨侧 gap 只需维护切分点 k 的一个有效区间；区间长度为 x 时，真正需要逐 k 处理的跨侧 gap 数量约为 `n/x`，整体线性。",
            ],
            "solution_brief": "关键观察：不要枚举所有切分点。先判断“完全有序仍可行”这一特殊分支：按连续 `-1` 段套 `2^len-len-1` 并加一。否则根据已知非固定点推断每个已知位置属于左/右侧；把相邻已知点之间的 `-1` 段按 `L->L`,`L->R`,`R->L`,`R->R` 分类，同侧 gap 的贡献独立相乘，跨侧 gap 只收缩切分点范围并在有效范围内累加组合数。",
            "primary_topic": "组合计数与概率",
        },
        "2147B": {
            "statement_brief": "构造长度 `2n` 的数组，使 `1..n` 每个数恰好出现两次，并且数 x 的两次出现位置距离能被 x 整除。",
            "transformed_statement": "把题目先看成：把两个 n 放在相距 n 的位置上作为中心，其它数左右镜像安排，使距离变成 `2x`。",
            "key_observations": [
                "令数组为 `[n,n-1,...,1,n,1,2,...,n-1]`。",
                "两个 n 出现在第 1 位和第 `n+1` 位，距离正好是 n。",
                "对任意 `1<=x<n`，它第一次在左半倒序中，第二次在右半正序中，两个位置距离为 `2x`。",
                "`2x` 一定能被 x 整除，因此这个固定构造对所有 n 都合法。",
            ],
            "solution_brief": "关键观察：直接输出固定模式即可。先输出 `n,n-1,...,1`，再输出 `n,1,2,...,n-1`；逐数检查距离分别为 n 或 `2x`。",
            "primary_topic": "构造与贪心",
        },
        "2138C2": {
            "statement_brief": "根树每个点要标 0 或 1，且恰好有 k 个 0。每个叶子的名字是根到叶路径标签串，要求最大化所有叶子名字的最长公共子序列长度。",
            "transformed_statement": "把题目先看成：所有叶子共同经过的只有深度不超过最浅叶子的各层；若这些层能按 0/1 整层染色，就能多拿一位公共子序列。",
            "key_observations": [
                "答案至少是最浅叶深度 D；若深度 `0..D` 的每一层都能选一个统一字符，则答案变成 `D+1`。",
                "设 `cnt[d]` 是深度 d 的点数；要把这些公共层整层染色，本质是问能否选择若干层作为 0，使其点数和不超过 k，且其它公共层点数和不超过 `n-k`。",
                "因此核心判定是一个层大小的子集和问题。",
                "困难版中层数和总权都可达 n，需要把相同层大小分组，用二进制拆分/根号分解配合 bitset 优化子集和。",
            ],
            "solution_brief": "关键观察：树形 LCS 先化成层计数背包。求最浅叶深度 D，统计 `0..D` 层大小，令总数为 sum。若 `sum<=k` 或 `sum<=n-k`，或者存在可达子集和 z 满足 `z<=k` 且 `sum-z<=n-k`，答案是 `D+1`；否则答案是 D。困难版用分组拆分后的 bitset 子集和实现。",
            "primary_topic": "动态规划与状态设计",
        },
        "2103D": {
            "statement_brief": "给数组 a，表示隐藏排列 p 中每个位置在交替删除“非局部最小/非局部最大”过程中的删除轮次，`-1` 表示最后留下。要求构造任意满足 a 的排列。",
            "transformed_statement": "把题目先看成：逐层递归构造；下一层留下的位置使用当前剩余最大的一批数，被本层删除的位置使用较小数并排成单调段。",
            "key_observations": [
                "任意相邻两个元素每轮至少删掉一个，所以删除轮次不会超过 `ceil(log2 n)`，并且同一层不能有相邻两个都继续留下的非法结构。",
                "若本层要留下 k 个位置，给它们分配当前最大的 k 个数，就能保证它们成为需要保留的局部极值。",
                "这些大数把本层被删除位置切成若干小段；小段内部只要单调，就不会额外产生不该保留的局部极值。",
                "前缀小段和后缀小段的单调方向要按当前层保留的是局部最大还是局部最小调整，避免端点误保留。",
            ],
            "solution_brief": "关键观察：构造顺序是按删除层递归，而不是猜整个排列。对当前层的位置集合，取 `a_i>layer` 的位置递归到下一层，并给它们最大的一批数；剩余要在本层删除的位置用较小数填。被保留位置分隔出的中间段随便按单调方向填，前缀升序、后缀降序等端点方向按层奇偶处理，最终得到合法排列。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2090C": {
            "statement_brief": "无限餐厅里桌子按每 `3*3` 格子中的四格出现。客人依次到来，类型 1 选最近空座位，类型 0 选最近完全没人坐过的桌子上的座位，距离和坐标字典序共同决定选择。",
            "transformed_statement": "把题目先看成：提前按真实行走距离排好所有可能被用到的桌格，再分别维护“任意空座”和“全新桌座”的最小可用指针。",
            "key_observations": [
                "桌格 `(x,y)` 的最短距离可直接写成 `x+y+2[x%3==2 且 y%3==2]`，不用在无限网格上搜索。",
                "前 n 个客人最多占用 n 个座位，只要预生成前 `4n` 个候选桌格就足够。",
                "类型 1 只要求座位未被占；类型 0 要求该座位所在整张桌子此前都未被占。",
                "每次选中一个座位后，把它标为已占，并把同桌四个座位在“全新桌”视角下全部标为不可用。",
            ],
            "solution_brief": "关键观察：距离排序可以离线完成，在线只移动两个指针。按距离、x、y 排出足够多的桌格；维护 `p0` 指向最小全新桌座，`p1` 指向最小空座。处理客人时跳过已不可用位置，输出当前格子，再更新普通占用和同桌全新状态即可。",
            "primary_topic": "构造与贪心",
        },
        "2082A": {
            "statement_brief": "给一个 0/1 矩阵，问最少翻转多少个格子，使每一行异或和、每一列异或和都等于 0。",
            "transformed_statement": "把题目先看成：只关心当前有多少坏行、多少坏列；翻一个格子会同时改变一行和一列的好坏状态。",
            "key_observations": [
                "设异或和为 1 的行数为 r，异或和为 1 的列数为 c。",
                "翻转一个格子会让它所在的一行和一列异或值各翻转一次。",
                "一次操作最多修好一个坏行和一个坏列，因此答案至少是 `max(r,c)`。",
                "当坏行和坏列数量不等时，多出来的坏行或坏列可以配好行/列一起翻，所以下界可达。",
            ],
            "solution_brief": "关键观察：不要枚举翻哪些格子。统计所有行异或和与列异或和，答案就是坏行数和坏列数的较大值；构造上可先一一配对坏行坏列，剩余的与好列或好行配对翻转。",
            "primary_topic": "基础实现与模拟",
        },
        "2064F": {
            "statement_brief": "给数组 a 和整数 k，统计有多少子数组能在某个切分点处满足“左半最小值 + 右半最大值 = k”。",
            "transformed_statement": "把题目先看成：每个合法子数组对应唯一一对 `(x,k-x)`，其中 x 是左侧最小值，`k-x` 是右侧最大值。",
            "key_observations": [
                "切分点从左到右移动时，左侧最小值和右侧最大值都单调不增。",
                "因此一个子数组若合法，其触发的 `(左最小,右最大)` 数值对是唯一的，不会被重复计数。",
                "固定 x 和 `y=k-x` 后，子数组必须同时包含 x 和 y，并且 x 左侧不能出现更小值，y 右侧不能出现更大值。",
                "枚举某个 x 作为子数组内第一个 x，左端可选范围由连续大于 x 的段决定，右端可选范围用 y 的位置、二分和前缀和统计。",
            ],
            "solution_brief": "关键观察：先用单调性避免重复，再按值对计数。对每个 x 令 `y=k-x`，枚举 x 的出现位置作为第一个 x；左端数量来自它左侧直到上一个 `<=x` 或上一个 x 的区间，右端数量来自后方可用 y 的覆盖长度，同时排除先遇到 `<x` 或 `>y` 的情况。所有位置贡献相乘累加。",
            "primary_topic": "数据结构",
        },
        "2047B": {
            "statement_brief": "给小写字符串，必须执行一次把某个位置改成另一个位置字符的操作，要求操作后字符串的不同排列数最少。",
            "transformed_statement": "把题目先看成：不同排列数只由各字符出现次数决定；让频率更集中会让排列数更少。",
            "key_observations": [
                "长度固定时，不同排列数为阶乘除以各字符频率阶乘的乘积。",
                "把一个低频字符改成高频字符，会减少字符种类或让频率分布更不均，从而不增加排列数。",
                "反过来，把高频改成低频或在相近频率间移动，都不会比“低到高”更优。",
                "题解的平局处理只是为了稳定输出：低频取较早字符，高频取较后字符，任意最优都可接受。",
            ],
            "solution_brief": "关键观察：操作目标是集中频率。统计 26 个字母频率，找出现次数最少且存在的字母、出现次数最多的字母；把任意一个最少字母位置改成最多字母即可。若本来只有一种字符，也可以选择同一位置，字符串不变。",
            "primary_topic": "构造与贪心",
        },
        "2039D": {
            "statement_brief": "给 n 和一个数集 S，要求构造字典序最大的数组 a，且每个 `a_i` 来自 S，并满足任意 `i<j` 都有 `a_gcd(i,j) != gcd(a_i,a_j)`。",
            "transformed_statement": "把题目先看成：原条件等价于所有整除关系 `i|j` 上都要求 `a_i` 不能整除 `a_j`。",
            "key_observations": [
                "若 `i|j`，原式变成 `a_i != gcd(a_i,a_j)`，也就是 `a_i` 不能整除 `a_j`。",
                "若某个非整除 pair 违反原条件，令 `g=gcd(i,j)`，由于 `a_g` 会同时整除 `a_i,a_j`，必然能降到 `(g,i)` 或 `(g,j)` 的整除关系违规。",
                "所以只需沿倍数链控制取值；一条从 1 到 x 的最长倍数链长度等于 x 的质因子总数加 1。",
                "为了字典序最大，第 i 位应取 S 中第 `p(i)+1` 大的数，其中 `p(i)` 是 i 的质因子重数。",
            ],
            "solution_brief": "关键观察：把全 pair 的 gcd 约束压成整除偏序约束。筛出每个 i 的质因子重数 `p(i)`；若 S 的大小小于 `floor(log2 n)+1` 则最长链上值不够用，输出 -1。否则令 `a_i` 为 S 中第 `p(i)+1` 大的元素，即 `s[m-p(i)]`，即可同时满足倍数链递减和字典序最大。",
            "primary_topic": "数论与同余",
        },
        "2258A": {
            "statement_brief": "数组中可多次选择奇数个下标并删除这些下标的中位下标对应元素，问最后剩余数组 gcd 的最大值。",
            "transformed_statement": "把题目先看成：首元素和尾元素永远删不掉，而中间任意元素都可以借助首尾一起被删掉。",
            "key_observations": [
                "删除操作选的是若干递增下标的中间那个，因此当前数组的第一个和最后一个元素不可能成为被删除元素。",
                "所以最终 gcd 一定要整除 `a_1` 和 `a_n`，上界是 `gcd(a_1,a_n)`。",
                "任意中间位置 i 都可以选择 `[1,i,n]` 这三个下标，把第 i 个元素删掉。",
                "重复删除所有中间元素后只剩首尾，正好达到这个上界。",
            ],
            "solution_brief": "关键观察：答案只由两端决定。首尾不可删除给出上界 `gcd(a_1,a_n)`；中间元素逐个用三元组 `[1,i,n]` 删除，因此能只保留首尾。输出 `gcd(a_1,a_n)`。",
            "primary_topic": "数论与同余",
        },
        "2245D1": {
            "statement_brief": "简单版给出所有 `(i,j)` 的限制：类型 1 要求 `a_i+a_j` 非负，类型 2 要求其为负。要求构造一个满足限制的数组或判无解。",
            "transformed_statement": "把题目先看成：先由自环限制确定每个数的正负，再把正数和负数之间的比较转成绝对值大小的有向约束图。",
            "key_observations": [
                "若存在解，就能把它扰动成所有 `|a_i|` 两两不同的解，因此非负约束可当成严格正来处理。",
                "`(i,i)` 的限制直接决定 `a_i` 是正数还是负数。",
                "当一个位置为正、另一个为负时，`a_i+a_j` 的符号等价于比较两者绝对值大小。",
                "把 `|a_u|<|a_v|` 作为有向边；若有环，绝对值大小矛盾，无解；否则拓扑序编号就是一组可行绝对值。",
            ],
            "solution_brief": "关键观察：限制不是数值方程，而是符号和绝对值偏序。先用每个 `(i,i)` 判正负；再遍历正负异号的限制，按和为正或负建立绝对值小于关系。若图不能拓扑排序则无解；否则按拓扑序给 `|a|` 赋 `1..n`，再乘上先前确定的符号输出。",
            "primary_topic": "图论与网络流",
        },
        "2223B": {
            "statement_brief": "数组 b 被随机排列后与固定数组 a 逐位相乘得到 c，要求 c 的逆序对数量期望。",
            "transformed_statement": "把题目先看成：期望按每个位置对线性拆开，问题变为统计多少四元组满足 `i<j` 且 `a_i*b_k > a_j*b_l`。",
            "key_observations": [
                "对固定位置对 `(i,j)`，随机排列会把任意有序且不同的 `(b_k,b_l)` 等概率放到这两个位置。",
                "所以总期望等于所有满足不等式的四元组数量除以 `n(n-1)`。",
                "不等式可改写成比例比较 `a_i/a_j > b_l/b_k`，从而把两个二次规模的分数数组排序后双指针计数。",
                "另一种做法是把所有 `(a_i*b_k,i)` 当作二维点数支配对，再扣掉 `k=l` 的重复使用情况。",
            ],
            "solution_brief": "关键观察：用期望线性性消掉排列。枚举所有 `i<j` 形成分数 `a_i/a_j`，枚举所有 `k!=l` 形成分数 `b_l/b_k`；排序后统计前者大于后者的配对数量，最后除以 `n(n-1)`。比较分数时用交叉乘法避免精度问题。",
            "primary_topic": "组合计数与概率",
        },
        "2222H": {
            "statement_brief": "对数组反复应用计数函数 f，`g(a)` 是过程中出现过的不同数组个数。给每维上界 `r_i`，要求按每个 p 统计 `g(a)=p` 的数组数量。",
            "transformed_statement": "把题目先看成：所有数组按 `a -> f(a)` 构成函数图，`g(a)` 就是 a 到根部循环前的深度加一。",
            "key_observations": [
                "函数图是一片伪森林：全零数组是孤点，`[1,0,0,...]` 是其它节点最终到达的根。",
                "直接刻画所有深度很难，但删去两层叶子后，只需枚举存在 b 使 `f(f(b))=a` 的核心数组。",
                "这个存在性等价于 `sum i*a_i <= n`，核心状态数等于若干整数分拆数量之和，n=50 时仍可枚举。",
                "预处理每个核心数组的深度后，再用动态规划统计满足 `f(f(b))=a` 且 `b_i<=r_i` 的原数组数量。",
            ],
            "solution_brief": "关键观察：不要在原数组空间里暴力走函数图。先枚举所有满足 `sum i*a_i<=n` 的核心数组，并求它们在函数图中的深度；除特殊根外，任意 b 若二次映射到 a，则 `g(b)=g(a)+2`。对每个核心 a，用按值从大到小填计数数组的 DP 统计有多少 b 受上界 r 限制，最后按深度归入答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2163E": {
            "statement_brief": "通信式交互题。第一次运行的玩家 A 看完整 0/1 网格，只能发一行一列；第二次运行的玩家 B 只看到这行和这列的值且不知道编号，要判断所有 1 是否连通。",
            "transformed_statement": "把题目先看成：A 要把真实答案编码进 B 能看到的“行首值是否与整列一致”这个一比特特征里。",
            "key_observations": [
                "若第一列同时有 0 和 1，A 固定发送第一列，并按答案选择行首值为特定 0 或 1 的行。",
                "B 只需比较收到的列中是否存在与行首不同的值，就能从约定规则恢复答案。",
                "若第一列全为同一值，则 A 根据答案选择第一列或某个含相反值的列，让 B 仍能看到“整列是否全等于行首”的区别。",
                "题目保证至少有一个 1，使全 0 等边界情况不会破坏这套编码。",
            ],
            "solution_brief": "关键观察：不要试图让 B 真正重建连通性，A 只需传递答案。A 先算出网格连通性；若第一列混有两种值，发第一列和行首值匹配约定答案的行。若第一列全同，则按答案选择第一列或一个含相反值的列。B 比较列是否全等于行首，即可输出约定结果。",
            "primary_topic": "交互",
        },
        "2159E": {
            "statement_brief": "给二次多项式 `a x^2+b x+c`，在线询问其 n 次幂的前 k 项系数和，询问会被上一问答案加密。",
            "transformed_statement": "把题目先看成：需要支持很多在线的单点系数查询；把 n 拆成大块和小块后，只取乘积中的一个系数。",
            "key_observations": [
                "两个多项式乘积的某一个系数只需枚举一边的有限项，不必完整卷积。",
                "预处理大块 `F(tB)` 和小块 `F(r)` 后，`F(n)=F(floor(n/B)*B)*F(n%B)`，每问只需 O(B) 合并一个系数。",
                "前缀系数和可定义成无限多项式 G，使 `[x^k]G(n)` 等于 `F(n)` 的前 k 项和，并满足 `G(n+m)=G(n)F(m)`。",
                "为了避免模数下快速卷积困难，题解用导数关系 `nF(n)(F(1))'=(F(n))'F(1)` 线性递推预处理各块。",
            ],
            "solution_brief": "关键观察：在线性来自大步小步分块，而不是每问重算幂。取块长 B；预处理所有小块 `F(0..B)` 和所有大块的前缀和多项式 `G(tB)`。查询 `(n,k)` 时拆成 `tB+r`，用 `G(tB)*F(r)` 的第 k 项得到答案。块多项式通过二次多项式的导数递推生成，整体约为 `O((N+Q)sqrt(N))`。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2159C": {
            "statement_brief": "给一个部分未知的多项式系数数组，定义孪生多项式为 `sum i*x^{a_i}`，要求补全后原多项式等于孪生多项式，统计方案数。",
            "transformed_statement": "把题目先看成：每个正下标 i 的系数只能是 0、自指向 i，或与另一个下标互相指向。",
            "key_observations": [
                "由等式可写成 `a_i = sum_{a_j=i} j`，也就是指向 i 的下标和必须等于 i。",
                "题解证明正下标只有三种结构：`a_i=0`、`a_i=i`、或 `a_i=j 且 a_j=i`。",
                "全未知时，新增第 i 个点可以置 0、自环，或与之前任一点配对，因此 `dp_i=2dp_{i-1}+(i-1)dp_{i-2}`。",
                "有已知值时，先检查它们是否只形成允许的自环或二元互换组件，剩余自由点再套同一个 DP。",
            ],
            "solution_brief": "关键观察：把系数看成函数图，而不是多项式运算。先按已知 `a_i` 建边并用并查集或组件检查排除非法：值越界、三元以上互指、固定关系不满足三种结构都无解。剩余未定正下标数量为 m 时，用 `dp_m=2dp_{m-1}+(m-1)dp_{m-2}` 计算补全方案。",
            "primary_topic": "组合计数与概率",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2147A": {
            "statement_brief": "从 `(0,0)` 出发，步长必须严格递增，方向按横向、纵向、横向交替。给目标 `(x,y)`，求最少步数或判不可达。",
            "transformed_statement": "把题目先看成：只需讨论 2 步和 3 步；更多步都能把末尾几步合并成更少步。",
            "key_observations": [
                "1 步不可能到达，因为 y 为正。",
                "2 步可达当且仅当先走 x、再走 y 且 `x<y`。",
                "3 步形如横向 a、纵向 b、横向 c，目标为 `(a+c,b)`，可把 a 调到 1，因此条件是 `x>y+1` 且 `y>1`。",
                "若步数超过 3，最后两步可与前面同方向步合并，得到更短方案，所以剩余情况无解。",
            ],
            "solution_brief": "关键观察：答案只可能是 2、3 或 -1。若 `x<y` 输出 2；否则若 `y>1` 且 `x>y+1` 输出 3；其它情况无法满足严格递增和交替方向，输出 -1。",
            "primary_topic": "构造与贪心",
        },
        "2146E": {
            "statement_brief": "对每个右端点 i，要求所有以 i 结尾的子数组中，权值的最大值；权值定义为子数组内大于最小未出现值的元素数量。",
            "transformed_statement": "把题目先看成：对每个候选缺失值 x，维护上一次出现 x 之后有多少元素大于 x。",
            "key_observations": [
                "计算权值时，可以枚举任意没有出现在子数组里的 x，并统计元素 `>x` 的数量；最大值会在真正的最小未出现值处达到。",
                "固定右端 r 和候选 x，最优左端就是上一次出现 x 的位置之后。",
                "加入新元素 v 时，对所有 `x<v`，这个新元素都会让计数加一。",
                "同时 x=v 重新出现，所有以当前右端结尾且缺 v 的子数组必须从当前位置之后开始，所以该计数清零。",
            ],
            "solution_brief": "关键观察：把每个 x 的最佳子数组贡献作为一个数组维护。扫描右端点，遇到 v 时对区间 `[0,v-1]` 加一，并把位置 v 赋为 0；每一步数组最大值就是答案。用支持区间加、单点赋值、全局最大值的数据结构即可。",
            "primary_topic": "数据结构",
        },
        "2130B": {
            "statement_brief": "给由 0、1、2 组成的数组和目标和 s，Bob 可重排数组，想让 Alice 从 1 走到 n 的相邻步路径无法得到总和 s；若能阻止则输出一种重排。",
            "transformed_statement": "把题目先看成：任意路径都是简单从左到右路径加上若干次相邻边的来回折返。",
            "key_observations": [
                "简单路径的和固定为数组总和，记为 base。",
                "每做一次相邻位置间的来回，多出来的和就是这两个相邻数的和。",
                "若 `s<base`，Alice 无论如何都到不了，任意排列即可。",
                "若 `s=base`，简单路径已经成功；若 `s-base>=2`，相邻边和能凑出目标增量。",
                "唯一可被 Bob 阻断的正增量是 1，只要避免 0 和 1 相邻即可。",
            ],
            "solution_brief": "关键观察：只需看 `d=s-base`。若 d 小于 0，输出任意排列；若 d 等于 1，输出所有 0、再所有 2、再所有 1，避免相邻和为 1；若 d 为 0 或至少 2，则 Alice 总能达到目标，输出 -1。",
            "primary_topic": "构造与贪心",
        },
        "2128E1": {
            "statement_brief": "给数组和最小长度 k，找最大的数 v，使某个长度至少 k 的子数组存在一个中位数为 v，并输出对应区间。",
            "transformed_statement": "把题目先看成：二分 v，只检查是否存在长度至少 k 的区间，其中 `>=v` 的数量不少于一半。",
            "key_observations": [
                "“存在子中位数至少为 v”随 v 单调，可以二分最大 v。",
                "把 `a_i>=v` 记为 +1，否则记为 -1；长度至少 k 的区间若和非负，就说明其中至少一半元素不小于 v。",
                "检查时扫描右端点，只需维护允许左端之前的最小前缀和。",
                "题解关键在于：对二分得到的最大 v，只检查 `>=v` 这一侧已经足够；若另一侧中位数条件失败，则 v 还能再增大，矛盾。",
            ],
            "solution_brief": "关键观察：不用同时维护大于和小于两套约束。二分 v 后构造 ±1 前缀和，扫描 r 时维护 `l-1<=r-k` 的最小前缀；若 `pref[r]-min_pref>=0` 就找到合法区间。二分结束时保存该区间，最大 v 自动是真正的子中位数。",
            "primary_topic": "数据结构",
        },
        "2127A": {
            "statement_brief": "数组含若干 `-1`，要把它们替换成非负整数，使任意连续三个数都满足“最小未出现值 = 最大值 - 最小值”。",
            "transformed_statement": "把题目先看成：任何合法三元组只能是三个相同的正数。",
            "key_observations": [
                "若三元组的最小未出现值为 0，则三元组里没有 0；要让最大值减最小值也为 0，三个数必须全相等。",
                "若最小未出现值不为 0，则三元组里有 0，此时最小值为 0，需要最小未出现值等于最大值。",
                "但最小未出现值本身不在三元组里，不可能又等于最大值。",
                "所以全数组可补全当且仅当所有已知非 `-1` 元素相同且不是 0。",
            ],
            "solution_brief": "关键观察：别枚举补值。删除所有 `-1` 后，若剩余不同值数量不超过 1，且其中没有 0，则可以把未知位置全部补成同一个正数；否则输出不可行。",
            "primary_topic": "构造与贪心",
        },
        "2124G": {
            "statement_brief": "数组可至多操作一次：选 `i<j`，把 `a_j` 加到 `a_i`，再把 `a_j` 置零。对每个最低代价 x，求代价至少 x 时前缀最小值总和的最大值。",
            "transformed_statement": "把题目先看成：只需要枚举少量有意义的 `(i,j)`，其中 i 是前缀最小位置，j 是后缀最大位置。",
            "key_observations": [
                "若 i 不是前缀最小，增加 `a_i` 不会改善任何前缀最小值。",
                "若 j 不是后缀最大，可以改用右侧更大的候选 j，收益不差且代价更大。",
                "固定 i 后，把 `a_i` 提到不同的下一层前缀最小值，只会对应少量后缀最大候选，总候选对仍是线性的。",
                "一次操作后的得分可拆成操作前前缀、被提高后的平坦段、后续前缀最小贡献，以及 j 置零造成的扣减。",
                "每个候选对只更新它的代价位置，最后对答案数组做后缀最大值即可满足“代价至少 x”。",
            ],
            "solution_brief": "关键观察：先把可选操作缩到线性规模。枚举前缀最小位置 i 和必要的后缀最大 j；用单调栈、前缀最小和、后缀贡献函数以及区间最小查询，快速计算该操作后的前缀最小值总和。把结果写入 `best[j-i]`，最后从右往左取后缀最大得到所有 x 的答案。",
            "primary_topic": "数据结构",
        },
        "2119B": {
            "statement_brief": "平面上从起点出发，依次走给定长度的线段，方向任意。问能否在所有步走完后正好到达终点。",
            "transformed_statement": "把题目先看成：再加一条从终点回到起点、长度为起终点距离的边，所有边能否首尾相接成闭合折线。",
            "key_observations": [
                "若最终能到终点，把终点到起点的向量补上后，总向量和为 0。",
                "这等价于给定这些边长能否组成一个可能退化的多边形。",
                "充要条件是最长边不超过其它边长度之和。",
                "为避免浮点误差，比较时可用距离平方，只在最终不等式中保持同一侧平方比较。",
            ],
            "solution_brief": "关键观察：方向自由后只剩边长闭合条件。令 d 为起点到终点的距离，`S=d+sum(a)`，`m=max(d,max(a))`；若 `m<=S-m` 则可达，否则不可达。实现中通常比较平方距离和整数边长，避免开方精度问题。",
            "primary_topic": "几何",
        },
        "2108C": {
            "statement_brief": "一排按钮有权值，克隆人经过未按按钮会立刻按下。要求按钮被按下的权值序列非递增，求最少需要创建几个克隆。",
            "transformed_statement": "把题目先看成：每个严格局部峰值都必须单独开一个克隆，其它位置可以从更高的邻居扩展过去。",
            "key_observations": [
                "连续相同权值的按钮不会改变答案，可以压缩成一个。",
                "压缩后，一个严格大于左右邻居的峰值不可能从旁边先走到，因为旁边权值更小，若先按旁边就会破坏非递增顺序。",
                "因此每个峰值至少需要一个克隆直接创建在它那里。",
                "非峰值位置至少有一个更高邻居或位于峰值扩展路径上，等更高按钮按完后移动过去即可。",
            ],
            "solution_brief": "关键观察：答案就是压缩后局部最大值个数。先去掉相邻重复值，在两端加很小的哨兵；扫描每个位置，若它严格大于左右邻居，就计入一个克隆。",
            "primary_topic": "构造与贪心",
        },
        "2085D": {
            "statement_brief": "传送带每分钟出现一盘寿司，拿一盘会增加 k 个待吃寿司；每分钟只能拿、吃或等待之一，最后必须吃完，求拿到美味值总和最大。",
            "transformed_statement": "把题目先看成：每拿一盘不仅占当前一分钟，还占未来 k 分钟吃完它，因此第 i 次从后往前数的拿盘时间有硬截止。",
            "key_observations": [
                "总共最多能拿 `floor(n/(k+1))` 盘，因为每盘需要一次拿取和 k 次吃。",
                "若还要拿第 i 盘，它最晚必须在第 `n-i*(k+1)+1` 分钟完成，否则剩余时间不够吃。",
                "扫描时间时，一旦到达某个截止点，就必须从此前出现且尚未选择的盘里确定一盘。",
                "为了最大化总美味，每次被截止逼迫选择时，都取此前未选盘中的最大美味。",
            ],
            "solution_brief": "关键观察：不是动态规划，而是按截止时间贪心。按分钟从前到后把当前美味值加入最大堆；当剩余分钟数刚好对应必须多选一盘的边界时，弹出堆顶加入答案。这样每次都在不违反吃完约束的前提下选到当前最优。",
            "primary_topic": "构造与贪心",
        },
        "2084B": {
            "statement_brief": "给正整数数组，问能否重排后存在切分点，使左半最小值等于右半所有数的最大公约数。",
            "transformed_statement": "把题目先看成：等式两边都必须等于全局最小值 x，右半只能从 x 的倍数里选。",
            "key_observations": [
                "任意一组数的最大公约数都不超过这组最小值；因此目标值不可能小于或大于全局最小值 x。",
                "至少要把一个 x 放在左半，保证左半最小值为 x。",
                "右半若要最大公约数为 x，只能使用 x 的倍数；加入非倍数会让最大公约数不是 x 的倍数。",
                "为了让右半最大公约数尽量降到 x，应把除掉一个 x 后所有 x 的倍数都放进去再取最大公约数。",
            ],
            "solution_brief": "关键观察：只检查全局最小值的倍数。设 x 为数组最小值，跳过一个 x，把剩下所有能被 x 整除的数取最大公约数；若结果为 x 则可行，否则不可行。若最小值出现至少两次，剩余倍数里会包含另一个 x，自然可行。",
            "primary_topic": "数论与同余",
        },
        "2077A": {
            "statement_brief": "原来有 `2n+1` 个两两不同的正整数，满足交错加减等式；现在删掉一个数并打乱剩余 `2n` 个，要求恢复任意一个原序列。",
            "transformed_statement": "把题目先看成：主动构造一个比所有已知数都大的“被删数”，这样不会和已知数冲突。",
            "key_observations": [
                "把等式变形后，可以把某个偶数位写成其它位置的线性组合。",
                "将最大已知数放在 `a_1`，再把接下来 n 个大数放在正号位置，小数放在负号位置。",
                "这样算出的缺失数等于“大数和减小数和”的形式，必然大于所有已知数。",
                "因为缺失数更大且所有输入数本来互异，构造出的 `2n+1` 个数也互异。",
            ],
            "solution_brief": "关键观察：不要猜原来删的是哪个数。排序后令最大数做 `a_1`，较大的 n 个数放到正号奇数位，较小的 `n-1` 个数放到负号偶数位；按变形公式计算新的缺失数并放到剩余偶数位。输出这个构造即可。",
            "primary_topic": "构造与贪心",
        },
        "2067B": {
            "statement_brief": "两个袋子中初始只有第一个袋子有数。可把数移到第二个袋子，也可把第一个袋子里一个在第二袋出现过的数加一。问能否最终两个袋子内容相同。",
            "transformed_statement": "把题目先看成：从小到大处理数值，每个数值至少要留下成对的一份，多余的同值数可以被加一传给下一个值。",
            "key_observations": [
                "一旦某个数被移到第二袋，它最终必须在第一袋里也保留一个相同数作为配对。",
                "因此当前最小值若只出现一次，就无法同时给两个袋子，必定失败。",
                "若当前值出现至少两次，可以固定一对；剩余同值数因为第二袋已有该值，都可以在第一袋中加一。",
                "按值从小到大重复这个过程，等价于把 `cnt[v]-2` 的多余数量转移到 `cnt[v+1]`。",
            ],
            "solution_brief": "关键观察：模拟频率流动即可。统计每个值出现次数，从小到大扫描；若某个当前频率为 1，输出不可行；若频率至少 2，就保留一对，并把多出的 `cnt[v]-2` 加到下一值频率。扫完没有单只残留则可行。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2063A": {
            "statement_brief": "区间 `[l,r]` 若端点互质则称为互质区间；若它不包含其它不同的互质子区间，则称为极小互质区间。问给定区间内有多少个极小互质区间。",
            "transformed_statement": "把题目先看成：长度至少 3 的互质区间一定包含相邻两个数，而相邻正整数永远互质。",
            "key_observations": [
                "任意相邻正整数 `x,x+1` 的最大公约数都是 1。",
                "因此长度超过 2 的互质区间一定包含一个更短的互质子区间，不可能极小。",
                "长度为 1 时，只有 `[1,1]` 的端点最大公约数为 1。",
                "长度为 2 时，所有 `[x,x+1]` 都互质；当 `x>1` 时它内部的单点都不互质，所以极小。",
            ],
            "solution_brief": "关键观察：极小互质区间只有 `[1,1]` 和所有 `[x,x+1] (x>1)`。若给定区间是 `[1,1]`，答案为 1；否则只需数有多少个相邻二元区间完全落在 `[l,r]` 内，答案为 `r-l`。",
            "primary_topic": "数论与同余",
        },
        "2061B": {
            "statement_brief": "给若干木棍长度，要求选 4 根组成面积为正的等腰梯形；矩形和正方形也算。若做不到输出 -1。",
            "transformed_statement": "把题目先看成：先找一对相等的腰，再让两条底边差值小于两倍腰长。",
            "key_observations": [
                "两底长度为 a、b，两腰长度为 c 时，面积为正的条件是 `|a-b|<2c`。",
                "若存在两组互不重叠的相同长度木棍，它们可直接组成矩形或等腰梯形。",
                "若没有任何相同长度对，则不可能有等腰梯形的两条腰。",
                "若只有一对相同长度 c，把它们当作腰，剩下只需找差值小于 `2c` 的两根底边；排序后检查相邻即可。",
            ],
            "solution_brief": "关键观察：问题核心是“腰相等 + 底边差别不能太大”。统计频率；有两对相同长度时直接输出。否则取唯一一对作为腰，删除后排序剩余长度，找任意相邻差值小于 `2c` 的两根作为底边；找不到则无解。",
            "primary_topic": "几何",
        },
        "2053H": {
            "statement_brief": "数组元素在 `[1,w]`。一次操作可选择一对相邻相等元素，把它们改成两个不同的新值。要求最大化最终元素和，并在达到最大和的前提下最小化操作次数。",
            "transformed_statement": "把题目先看成：有相邻相等才会产生操作能力；当 `w>=3` 且能操作时，目标最终形态几乎是全 w，只留下一个 `w-1`。",
            "key_observations": [
                "`w=2` 时，带两端哨兵后相邻不同的边数不会减少；每段连续 1 最终至少留下一个 1。",
                "`w>=3` 且没有相邻相等时，无法进行任何操作，答案就是原数组和与 0 次操作。",
                "若能操作且不是已经全 w，最大和为 `n*w-1`；最后一个不是 w 的位置承担“相邻操作后必须不同”的代价。",
                "最少操作数可反向理解：先把某个相邻相等对作为种子推到一端，再向另一侧扩展成目标形态。",
                "扩展路径上连续的 w 会带来额外操作；长度为 L 的阻塞 w 段贡献约为 `ceil(L/2)`，单点 w 还要特殊补一次。",
            ],
            "solution_brief": "关键观察：先分 `w=2`、无可操作、可操作三类。`w=2` 时答案为 `2n-连续1段数`，操作数为 1 的个数；`w>=3` 且可操作时，最大和通常是 `n*w-1`。为求最少操作，枚举从左或从右扩展的起始相等对，计算把相等关系推到边界再覆盖全数组的代价，并额外加上路径中 w 段的处理成本，取最小值。",
            "primary_topic": "构造与贪心",
        },
        "2048E": {
            "statement_brief": "要求给完全二分图的每条边染上 `1..n` 中的颜色，使任意同色边不形成环；若无法构造则输出不可行。",
            "transformed_statement": "本地只有题面和题解链接，没有可用题解正文；本条只保留题意，不补写关键观察。",
            "extraction_status": "missing_editorial",
            "primary_topic": "图论与网络流",
        },
        "2028C": {
            "statement_brief": "把蛋糕切成 `m+1` 个连续块，m 个客人各要至少 v 的美味值，Alice 可拿剩下一块且可为空。问 Alice 最多能拿多少美味值，若无法满足所有客人输出 -1。",
            "transformed_statement": "把题目先看成：Alice 拿的是某个中间子段，左右两侧必须合计能切出 m 块每块和至少 v 的蛋糕。",
            "key_observations": [
                "从左到右贪心切块能得到每个前缀最多喂饱多少客人，记为前缀可喂数。",
                "从右到左同理得到每个后缀最多喂饱多少客人。",
                "若 Alice 选择区间 `[i,j)`，只需满足左前缀和右后缀的可喂数之和至少为 m。",
                "固定左端 i 时，能保留给 Alice 的右端越靠右越好；后缀可喂数单调，可用双指针或二分找最大 j。",
            ],
            "solution_brief": "关键观察：不要枚举切法，而是枚举 Alice 的连续块。预处理前缀最多能切出的合格块数和后缀最多能切出的合格块数；对每个左端，用双指针找最远右端使两侧仍能喂饱 m 个客人，用前缀和计算 Alice 的块和并取最大。若没有可行块则输出 -1。",
            "primary_topic": "动态规划与状态设计",
        },
        "2256B": {
            "statement_brief": "长度 n 的 0/1/? 字符串中，替换所有问号后，相邻两个二元骨牌的权值必须不同。问合法替换方案数。",
            "transformed_statement": "把题目先看成：相邻骨牌权值不同等价于隔一个位置的字符必须不同。",
            "key_observations": [
                "相邻骨牌条件是 `s_i+s_{i+1} != s_{i+1}+s_{i+2}`。",
                "消去公共的 `s_{i+1}` 后得到 `s_i != s_{i+2}`。",
                "字符只有 0 和 1，因此 `s_{i+2}` 被 `s_i` 唯一确定。",
                "只要确定前两个字符，整个字符串都被强制确定，所以最多检查 4 种方案。",
            ],
            "solution_brief": "关键观察：问号不需要动态规划。枚举 `s_1,s_2` 的四种取值，按 `s_{i+2}=1-s_i` 推完整串；若与原有确定字符都不冲突，就计入答案。答案最多为 4。",
            "primary_topic": "基础实现与模拟",
        },
        "2249C": {
            "statement_brief": "排列写在环上，从某个起点顺时针读一整圈。若每个前缀已出现值集合都能分成不超过两个连续值段，则该起点合法。问合法起点数。",
            "transformed_statement": "把题目先看成：把环复制成长度 `2n` 的序列，同时维护所有起点当前前缀的连续值段数量。",
            "key_observations": [
                "插入新值 x 时，连续值段数量先加一；若 `x-1` 已出现则少一个段，若 `x+1` 已出现也少一个段。",
                "对固定右端 r，可能起点只是一段区间 `[max(1,r-n+1), min(r,n)]`。",
                "某个邻值是否已出现在该起点的前缀里，只取决于该邻值上一次出现位置是否不小于起点。",
                "因此一次插入 x 可以转成至多三次区间加法，批量更新所有起点的段数。",
                "起点一旦出现过超过两个段，之后即使段数下降也已经不合法，可以永久删除。",
            ],
            "solution_brief": "关键观察：同时处理全部起点。复制排列，扫右端 r；对所有可覆盖起点区间加一，再按 `x-1/x+1` 的最近出现位置对前缀起点区间减一。用懒标记线段树维护每个起点当前段数和最大值，凡最大值超过 2 就删除对应起点，最后剩余数量即答案。",
            "primary_topic": "数据结构",
        },
        "2247C": {
            "statement_brief": "给两个 0/1 数组 a、b。一次操作可选择当前 a 中元素和为奇数的非空子序列，并翻转这些位置。求把 a 变成 b 的最少操作数或判无解。",
            "transformed_statement": "把题目先看成：只需要看所有不匹配位置在当前 a 中的 1 的个数奇偶，答案只可能是 0、1、2 或 -1。",
            "key_observations": [
                "若 `a=b`，不需要操作。",
                "若 a 中没有 1，则无法执行任何有效操作；若 b 全是 1，也不可能作为一次翻转后的目标。",
                "设所有不匹配位置组成集合 D；如果 D 中 a 的和为奇数，一次翻转 D 即可。",
                "若这个和为偶数但不是无解，可借助一个本来相同的 0 位和一个本来相同的 1 位，把操作拆成两次。",
            ],
            "solution_brief": "关键观察：无需构造具体子序列。先处理相等和无解条件；计算所有 `a_i!=b_i` 位置的 `a_i` 之和。若为奇数答案 1，否则答案 2，因为可用一对保持位作为中转，让两次操作的选择和都为奇数。",
            "primary_topic": "构造与贪心",
        },
        "2247B": {
            "statement_brief": "构造长度 n 的正整数数组，使最短的非空连续子数组中，能被 m 整除的和的长度恰好为 k；若无法构造则输出不可行。",
            "transformed_statement": "把题目先看成：要让任意长度小于 k 的子数组和都在 `(0,m)` 内，而每个长度 k 的块和正好等于 m。",
            "key_observations": [
                "若 `k>m`，任意长度 m 的正整数数组按前缀和取模必有一个非空子数组和被 m 整除，且长度小于 k，必定无解。",
                "当 `k<=m` 时，可以让每 k 个位置形成总和 m。",
                "构造中大部分位置填 1，每个第 k 个位置填 `m-k+1`。",
                "任意长度小于 k 的子数组和为正且小于 m，长度 k 的子数组和则正好为 m。",
            ],
            "solution_brief": "关键观察：前缀和抽屉给出无解边界，周期构造给出可行解。若 `k>m` 输出不可行；否则按周期输出：位置编号能被 k 整除时填 `m-k+1`，其它位置填 1。",
            "primary_topic": "构造与贪心",
        },
        "2222D": {
            "statement_brief": "给数组 a。排列 p 的每个逆序对 `(i,j)` 贡献 `sum(a_i..a_{j-1})`，要求构造使总贡献最大的排列。",
            "transformed_statement": "把题目先看成：逆序对 `(i,j)` 的贡献等于两个前缀值 `b_j-b_i`，因此应让前缀值大的位置拿更小的排列值。",
            "key_observations": [
                "定义 `b_i=sum_{t< i} a_t`，则区间贡献可写成 `b_j-b_i`。",
                "若 `b_j>b_i`，希望 `(i,j)` 成为逆序对来获得正贡献。",
                "若 `b_j<b_i`，希望它不是逆序对，避免负贡献。",
                "这等价于让 p 的大小顺序与 b 的大小顺序相反。",
            ],
            "solution_brief": "关键观察：排序前缀值即可同时满足所有 pair 的最优方向。计算每个位置 i 的前缀值 `b_i`，按 `b_i` 从大到小排序位置，并依次赋排列值 `1,2,...,n`；前缀值越大，排列值越小。",
            "primary_topic": "构造与贪心",
        },
        "2222B": {
            "statement_brief": "每次可选择一个奇长区间并翻转其左右对称位置，然后标记给定下标处的元素。标记跟随元素移动。要求 m 次后未标记元素和最小。",
            "transformed_statement": "把题目先看成：奇长翻转不会改变下标奇偶，因此第 x 次只能从与 x 同奇偶的位置集合中挑一个元素送去被标记。",
            "key_observations": [
                "奇长中心翻转中，所有元素只会在同奇偶下标之间移动。",
                "同奇偶位置之间可以通过一次合适翻转把任意元素移动到目标下标。",
                "为了让未标记和最小，应优先标记当前同奇偶组中最大的未标记正数。",
                "如果该奇偶组还没有标记过，即使最大值非正也必须标记一个；之后若最大未标记值非正，可以重复标记已标记元素来避免损失。",
            ],
            "solution_brief": "关键观察：把数组按下标奇偶拆成两个可任意调度的集合。按操作给出的 x 的奇偶处理对应集合：若还有正数未标记，标记最大正数；若该集合第一次出现，标记其中最大值；否则重复标记旧元素。最后用总和减去被标记元素和得到最小未标记和。",
            "primary_topic": "构造与贪心",
        },
        "2216A": {
            "statement_brief": "有 n 门课，每门课有优先级 `1..k+1`，前 k 级有容量限制。一次操作只能把一门课优先级加 1，过程中始终不能违反容量。要求在 1000 次内把所有课调到第 `k+1` 级。",
            "transformed_statement": "把题目先看成：从高编号优先级往低编号处理，每次把当前级别的课一路向下挪到无限容量级。",
            "key_observations": [
                "第 `k+1` 级没有容量限制，是所有课程的终点缓冲区。",
                "从第 k 级开始清空时，课程只会进入第 `k+1` 级，不会占用受限容量。",
                "清空第 i 级前，所有更低优先级编号更大的受限级别已经被清空，因此一路增加不会造成容量超限。",
                "每门课最多被操作 k 次，总操作数不超过 `n*k<=1000`。",
            ],
            "solution_brief": "关键观察：顺序必须从 k 到 1。对级别 i 从 k 递减到 1，枚举所有当前在 i 级的课程，把它连续操作到 `k+1` 级并记录课程编号。因为经过的更低优先级受限层已被清空，所以每一步都合法。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2208D2": {
            "statement_brief": "给一个有向树的可达性矩阵，要求判断是否存在某棵无向树定向后得到它，并构造这棵有向树。",
            "transformed_statement": "把题目先看成：在可达偏序里恢复树边，也就是对每个点找它直接可达的儿子，去掉能经中间点到达的传递边。",
            "key_observations": [
                "若有解，边结构唯一，因为树上的可达关系决定了每个点的直接后继。",
                "朴素判定边 `u->v` 是：u 能到 v，且不存在中间点 w 满足 `u->w->v`。",
                "困难版对每个 u 不直接三重循环；先按可达集合大小从大到小枚举候选 v。",
                "每选到一个最大可达候选 v，就加入边 `u->v`，然后把 v 能到的所有点从 u 的待处理集合中删除。",
                "最后边数必须为 `n-1`、连通且重新 DFS 得到的可达矩阵要和输入完全一致。",
            ],
            "solution_brief": "关键观察：矩阵要做的是有向树的传递约简。对每个 u，按可达节点数从大到小扫描 v；若 v 仍未被某个已选儿子覆盖且 `u` 可达 `v`，就把 `u->v` 作为直接边，并标记所有 `v` 可达点为已覆盖。全部边生成后检查边数、无向连通性和实际可达矩阵，全部通过才输出。",
            "primary_topic": "树结构",
        },
        "2205B": {
            "statement_brief": "给整数 n，求最小正整数 k，使得 n 能整除 `k^n`。",
            "transformed_statement": "把题目先看成：k 只需要包含 n 的每一种质因子一次。",
            "key_observations": [
                "若 `n=prod p_i^{a_i}`，要让 `n | k^n`，每个质因子 `p_i` 必须出现在 k 中。",
                "反过来，取 `k=prod p_i` 时，`k^n` 中每个 `p_i` 的指数都是 n，足以覆盖 `a_i<=n`。",
                "因此答案就是 n 的不同质因子的乘积，也就是 n 的 square-free kernel。",
                "`n<=1e9` 时试除到平方根即可；剩余大于 1 的部分就是最后一个大质因子。",
            ],
            "solution_brief": "关键观察：指数不需要精确配，只要每个质因子出现一次。试除 n，每遇到一个质因子 p 就把答案乘 p，并把 n 中所有 p 因子除尽；循环结束若剩余 n 大于 1，再乘上它。",
            "primary_topic": "数论与同余",
        },
        "2183D2": {
            "statement_brief": "根树初始全白。每次可染黑一组白点，要求组内任意两点深度不同且不相邻。困难版要求用最少次数染黑整棵树并输出方案。",
            "transformed_statement": "把题目先看成：给每个点分配一个操作编号，同深度和父子相邻的点不能同编号；目标是最少颜色数并构造分组。",
            "key_observations": [
                "任一深度上有 `t_d` 个点，所以操作数至少是最大层宽 T。",
                "题解证明答案最多只会是 T 或 `T+1`。",
                "先把最大层的点分别放进 T 个集合，再向下逐层放子节点：同父的多个孩子只保留一个受父集合限制，其余放进空闲集合。",
                "向上处理父节点时，如果下一层所有 T 个集合都被同一个父亲的孩子占住，就必须新开第 `T+1` 个集合。",
                "另一种视角是逐层做颜色分配：同层颜色互异，且避开父亲颜色；每层可转成一个有禁色的匹配/轮换问题。",
            ],
            "solution_brief": "关键观察：最少操作数由最大层宽控制，只在一个特殊阻塞情形多 1。按深度分层，先固定最大层的 T 个集合；往深层和浅层扩展时，维护每个点所在集合，父子不能同集合，同层自然分散。遇到某层父节点被下一层全部集合堵住时新开集合，否则把父节点轮换进可用集合，最终输出每个集合内的点。",
            "primary_topic": "树结构",
        },
        "2178B": {
            "statement_brief": "字符串只含 `s/u`。可把任意字符改成 `s`，要求最少操作使字符串中至少两个 s，且每个 u 到最近两个 s 的距离相等。",
            "transformed_statement": "把题目先看成：合法串等价于首尾都是 s，且不存在相邻的 u。",
            "key_observations": [
                "一个 u 的两个最近 s 必须分别在它左右两侧，不能都在同一边。",
                "因此首尾不能是 u，否则它没有两侧的 s。",
                "若某个 u 旁边还有 u，那么连续 u 段端点一定无法满足两侧最近 s 等距。",
                "若每个 u 左右都是 s，则它最近的两个 s 距离都为 1，条件成立。",
                "所以最少修改就是改首尾 u，再把每段连续 u 中每两个改掉一个。",
            ],
            "solution_brief": "关键观察：把定义化成局部模式。先把首尾若为 u 改成 s；然后从左到右扫描，若当前位置和前一位置在当前修改后都是 u，就把当前位置改成 s 并计数。等价地，每段内部连续 u 长度 L 贡献 `floor(L/2)`。",
            "primary_topic": "字符串",
        },
        "2164A": {
            "statement_brief": "给序列 a 和目标 x。每次可把相邻两个数合并成位于二者最小值和最大值之间的任意整数，问最后能否剩下 x。",
            "transformed_statement": "把题目先看成：合并操作永远不会把当前所有数的取值范围扩大；但范围内任意 x 都能保留下来。",
            "key_observations": [
                "任何合并结果都在被合并两数之间，所以最终值不可能小于全局最小值或大于全局最大值。",
                "若存在一个数不超过 x、一个数不小于 x，就能保留这两个代表值到最后。",
                "合并其它元素时，总可以让代表值不变：把它和邻居合并后仍取代表值。",
                "最后只剩一个不超过 x 和一个不小于 x 的数时，合并成 x 即可。",
            ],
            "solution_brief": "关键观察：答案只看 x 是否在数组最小值和最大值之间。若 `min(a)<=x<=max(a)` 输出 YES，否则输出 NO。",
            "primary_topic": "基础实现与模拟",
        },
        "2159A": {
            "statement_brief": "交互题。隐藏长度 `2n` 的序列，每个 `1..n` 恰好出现两次；一次询问返回所选下标子序列中出现至少两次的最大值。要求在 `3n` 次询问内还原序列。",
            "transformed_statement": "把题目先看成：维护一个询问结果为 0 的下标集合 S，也就是 S 中每个值至多出现一次。",
            "key_observations": [
                "若 `MAD(S)=0`，再加入一个新下标 i 后结果变成非零 x，则只能是 `a_i=x` 造成了重复。",
                "若结果仍为 0，说明 i 的值尚未在 S 中出现，可以把 i 加入 S。",
                "第一轮扫所有下标，会识别每个值第二次出现的位置；此时 S 恰好包含每个值一次。",
                "把 S 换成它的补集后，补集也恰好包含每个值一次；再扫未确定位置，每次加入都会立刻暴露其值。",
            ],
            "solution_brief": "关键观察：用 `MAD=0` 集合当作字典。第一遍从空 S 开始，对每个 i 查询 `S∪{i}`；非零则确定 `a_i`，否则把 i 放入 S。第一遍结束后 S 和补集各含每个值一次，再令 S 为补集，对未确定下标重复同样查询，正好在 `3n` 次内确定全部值。",
            "primary_topic": "交互",
        },
        "2150B": {
            "statement_brief": "在 `n*n` 网格中染黑若干格。每行黑格数必须等于给定 `a_i`，且对每个 k，满足 `max(x,y)=k` 的黑格恰好一个，满足 `max(x,n+1-y)=k` 的黑格也恰好一个。问合法网格数。",
            "transformed_statement": "把题目先看成：后两个条件会强制每一列恰好选一个黑格，且第 j 列可选行数有上界。",
            "key_observations": [
                "由 `max(x,y)=1` 可知 `(1,1)` 必黑，进一步推出第 1 列其它行必白。",
                "类似向右推进可得第 j 列只能在 `i<=j` 的行里选黑格。",
                "从右侧对称推进，又得到第 j 列还必须满足 `i<=n-j+1`。",
                "所以每列 j 恰好选一个行 `i<=min(j,n-j+1)`。",
                "按行从下往上分配列：第 i 行可用列数扣掉更低行已占列后，选择 `a_i` 个即可。",
            ],
            "solution_brief": "关键观察：先由对角条件推出可选区域，再按行计数组合数。对每一行 i 从 n 到 1 处理，维护当前还能放到第 i 行或更高行的列数 `c_i`；若 `a_i>c_i` 则无解，否则乘上组合数 `C(c_i,a_i)` 并把这些列从后续可用数中扣掉。",
            "primary_topic": "组合计数与概率",
        },
        "2146F": {
            "statement_brief": "对排列的每个前缀运行冒泡排序，记需要的轮数为 `b_i`。给若干限制，要求统计满足“`b_y<=k` 的位置数量在区间内”的排列数。",
            "transformed_statement": "把题目先看成：排列可等价编码为每个位置左侧比它大的元素个数 `c_i`，而 `b_i` 就是 `c` 的前缀最大值。",
            "key_observations": [
                "冒泡排序中，一个元素每轮最多越过一个在它左侧且比它大的元素，所以总轮数是所有 `c_i` 的最大值。",
                "对前缀 `1..i`，轮数就是 `max(c_1..c_i)`。",
                "数组 c 满足 `0<=c_i<i`，并且它与排列一一对应，相当于逆序序列。",
                "限制只涉及若干 k 下 `b_i<=k` 的位置数量，因此只需在这些分界点上做区间 DP。",
                "一整段下标内若要求最大 c 不超过 t，方案数是 `prod min(i,t+1)`，可用阶乘和快速幂快速计算。",
            ],
            "solution_brief": "关键观察：先把排列计数换成逆序序列计数。根据所有限制的端点和值把下标和值域都切成 `O(m)` 段，令 DP 状态表示处理到某个下标段且当前前缀最大 c 落在哪个值域段。段转移用 `calc(l,r,t)` 计算这一段所有 `c_i<=t` 的填法，差分得到最大值首次落入某值域段的方案，最后筛掉不满足限制的状态。",
            "primary_topic": "组合计数与概率",
        },
        "2146D2": {
            "statement_brief": "给区间 `[l,r]`，数组 b 固定为 `l..r`，可任意重排数组 a，最大化 `sum(a_i | b_i)` 并输出一种最优重排。",
            "transformed_statement": "把题目先看成：按最高不同二进制位把区间切成左右两半，优先把低半和高半配成按位互补。",
            "key_observations": [
                "按位看，`a|b = a+b-(a&b)`，最大化 OR 等价于尽量让配对的公共 1 位少。",
                "设最高不同位为 x，令 t 为该位从 0 变 1 的边界；`x<t` 的左半和 `>=t` 的右半在这一位互补。",
                "把数 y 和 `2t-1-y` 配对时，低于 x 的位也互补，因此这些位的按位与为 0。",
                "哪边短就把哪边全部配掉，剩下未处理的仍是一个连续区间，可以递归继续。",
                "单点区间直接自配即可。",
            ],
            "solution_brief": "关键观察：最优构造是递归互补配对。当前区间找最高不同位和边界 t；若左半短，就把 `[l,t-1]` 与 `[t,2t-1-l]` 反向配对，否则把右半与 `[2t-1-r,t-1]` 反向配对。配掉部分后对剩余连续区间继续处理，最终得到重排和最大值。",
            "primary_topic": "构造与贪心",
        },
        "2109A": {
            "statement_brief": "n 个玩家相邻对战 `n-1` 场，每人报告自己是否至少赢过一场。问是否能确定至少有人说谎。",
            "transformed_statement": "把题目先看成：真实报告必须同时满足“不是全 1”和“没有相邻两个 0”。",
            "key_observations": [
                "总共只有 `n-1` 场比赛，因此不可能 n 个人都至少赢过一场。",
                "若相邻两个人都报告 0，他们之间的那场比赛必有一人获胜，矛盾。",
                "除此之外的报告模式都可以安排比赛胜负与之匹配。",
            ],
            "solution_brief": "关键观察：只查两个必然矛盾。若所有 `a_i` 都是 1，输出 YES；若存在相邻两个 0，也输出 YES；否则无法证明有人说谎，输出 NO。",
            "primary_topic": "基础实现与模拟",
        },
        "2103F": {
            "statement_brief": "给 k 位整数数组。对每个位置 i，求所有包含 i 的子数组按从左到右累计 bitwise NOR 后能得到的最大值。",
            "transformed_statement": "把题目先看成：固定右端 r 时，所有区间 `[l,r]` 的 NOR 取值只有 `O(k)` 种，变化点只在各 bit 最近一次出现 1 的附近。",
            "key_observations": [
                "若能快速求任意区间 NOR，就可以把候选区间值批量更新到其覆盖的位置答案上。",
                "对单个 bit，区间 NOR 的结果只取决于这个 bit 在右端 r 之前最近一次 1 的位置，以及区间长度奇偶。",
                "当左端 l 每次左移 2 时，奇偶关系不变；除非跨过某个 bit 的最近 1 位置，NOR 值不会改变。",
                "所以固定 r 只需检查每个 bit 最近 1 位置附近的少量左端，再加上 l=1。",
                "每个候选区间 `[l,r]` 的 NOR 值可以用预处理的最近 1 位置逐 bit 算出，并更新它覆盖的所有下标。",
            ],
            "solution_brief": "关键观察：枚举右端但不枚举所有左端。维护 `pref[r][bit]` 表示每个 bit 到 r 为止最近的 1；对每个 r，只测试所有 `pref[r][bit]+[-2..2]` 这类变化点和 1，算出对应区间 NOR。用支持区间取 max 的线段树把该值更新到 `[l,r]`，最后每个位置取最大值。",
            "primary_topic": "数据结构",
        },
        "2103B": {
            "statement_brief": "二进制打字机初始手指在 0 上，按当前键和切换键都算一次操作。允许至多反转一个子串，求打完整个字符串的最小代价。",
            "transformed_statement": "把题目先看成：总要按 n 次键，优化空间只在减少相邻字符变化次数上。",
            "key_observations": [
                "不反转时，切换次数等于在字符串前补一个 0 后的相邻变化次数。",
                "反转子串内部的相邻变化次数不变，只有子串两端边界会变化。",
                "一次反转最多让两个边界各少一次变化，因此最多减少 2 次切换。",
                "若原变化次数至少 3，一定能减少 2；若等于 2，只能减少 1；若为 0 或 1，则无法减少。",
            ],
            "solution_brief": "关键观察：不用枚举反转区间。令 `cnt` 为字符串前加 0 后的相邻变化次数；基础代价是 `n+cnt`。若 `cnt>=3`，答案 `n+cnt-2`；若 `cnt==2`，答案 `n+cnt-1`；否则答案保持 `n+cnt`。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2084H": {
            "statement_brief": "给一个二进制序列。一次操作选连续三个位置，删掉其中最左边的中位数字。问经过任意次操作后能得到多少种不同二进制序列。",
            "transformed_statement": "把题目先看成：把原串压成相同字符连续段长度数组，删除操作只是在这些段长上做递减或合并。",
            "key_observations": [
                "若某段长度至少 2，可以直接把该段长度减 1。",
                "若相邻两段长度都为 1，删除前一段后会让两侧同字符段合并。",
                "最后一段长度不会增加，而且与前面段的生成过程相对独立，可以先乘上最后一段可选长度。",
                "固定结果串首字符时，可贪心找原段长数组中能生成它的最短前缀，并用 DP 统计下一段长度的选择数。",
                "若结果串首字符与原串不同，则必须先删掉第一段，这要求第二段长度最多为 1，然后转化为同样 DP。",
            ],
            "solution_brief": "关键观察：不要在原字符串上搜，先压缩成段长。对同首字符的结果做段 DP：`f_i` 表示结果当前最后一段匹配到原第 i 段的方案数，转移只从奇偶相反的后续段来，并统计可生成的新段长范围。异首字符情况等价于删除第一段并把第二段视作长度 1 后再跑同一过程。题解再用 `nxt` 跳转和差分把二次 DP 优化到线性。",
            "primary_topic": "动态规划与状态设计",
        },
        "2084E": {
            "statement_brief": "给一个含 `-1` 的 0 到 n-1 排列，要求对所有合法补全排列，求所有非空子段 MEX 之和的总和。",
            "transformed_statement": "把题目先看成：MEX 贡献可拆成“0..k 是否全在当前子段里”的指示函数之和。",
            "key_observations": [
                "`mex(segment)=sum_k [0..k 全部出现在 segment 中]`，于是可以按 k 和子段计贡献。",
                "对固定子段 `[l,r]` 和 k，已经出现的 `0..k` 必须全部落在 `[l,r]` 内。",
                "若 `[l,r]` 内有 `c1` 个空位，`0..k` 中缺失的数有 `c2` 个，则补全贡献为 `C(c1,c2)*c2!*(t-c2)!`。",
                "因此核心变成统计：对每个空位数 c1 和阈值 k，有多少子段包含所有已出现的 `0..k`。",
                "枚举子段时可算出它含有的空位数 x，以及第一个未被包含的已知小值 y，把贡献批量加到 `d[x][0..y-1]`。",
            ],
            "solution_brief": "关键观察：按 MEX 的指示函数展开后，补全排列数只依赖子段空位数和缺失小数个数。枚举所有子段，维护其中空位数量和没有被子段覆盖的最小已知值，更新计数表 `d`；最后对每个 `(c1,k)` 乘上选择缺失小值填入子段空位的组合数和剩余空位排列数，累加即答案。",
            "primary_topic": "组合计数与概率",
        },
        "2053D": {
            "statement_brief": "给数组 a、b。可任意重排 b，使 `prod min(a_i,b_i)` 最大；随后多次把 a 或 b 的某个原位置加一，每次输出最大乘积模数。",
            "transformed_statement": "把题目先看成：两边都排序后同位配对最优，单点加一只会把排序数组中同值段最后一个元素加一。",
            "key_observations": [
                "若排序后的 a、b 中存在交叉配对 `c_i<c_j` 但 `d_i>d_j`，交换 `d_i,d_j` 不会让乘积变小。",
                "所以最大值由两个数组分别升序排序后逐位取 `min` 得到。",
                "某个原值 x 加一时，在排序数组中应修改值为 x 的最右位置；这样加一后数组仍保持有序。",
                "只有该位置的 `min(c_p,d_p)` 可能变化，因此可用乘法逆元把答案中旧因子替换成新因子。",
            ],
            "solution_brief": "关键观察：维护排序后的多重集视图。初始排序 a、b 并计算乘积。修改 a[x] 时，在排序数组 c 中找到原值 `a[x]` 的最后一个位置 p；若 `c_p<d_p`，答案乘上 `inv(c_p)*(c_p+1)`，再把该位置和原数组值加一。修改 b 对称处理。",
            "primary_topic": "数据结构",
        },
        "2049D": {
            "statement_brief": "网格每行可在出发前循环左移任意次，每次位移花费 k。之后只能向右或向下走到右下角，路径代价为位移花费加经过格子和，求最小代价。",
            "transformed_statement": "把题目先看成：进入每一行时单独选择该行的循环位移，然后在这一行内向右走若干步再下去。",
            "key_observations": [
                "每一行的位移只影响这一行访问到的格子，与其它行的位移选择独立。",
                "令 `f(i,j)` 表示处理完第 i 行到达列 j 的最小代价。",
                "令 `g(i,j,x)` 表示第 i 行左移 x 后，在该行内走到列 j 的最小代价。",
                "转移只有两种来源：从上一行同列下移进入，或从本行左侧继续右移。",
                "枚举每行位移 x 和列 j，即可在 `O(n*m^2)` 内完成。",
            ],
            "solution_brief": "关键观察：位移作为行内状态枚举，不需要把所有行的位移组合起来。对每行 i 枚举 shift，初始化 `tmp[j]=f[i-1][j]+k*shift+a[i][(j+shift)%m]`，再沿行向右松弛 `tmp[j]`；用所有 shift 的 tmp 更新 `f[i][j]`。最终答案为 `f[n][m]`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2029D": {
            "statement_brief": "给无向图。一次操作选择三个点并翻转三角形三条边的存在性，要求在操作次数限制内把图变成空图或树。",
            "transformed_statement": "把题目先看成：先用三角翻转把图降成度数最多 1 的匹配，再把这些小连通块接成一棵树。",
            "key_observations": [
                "若某点 u 度数至少 2，取两个邻居 v、w，对 `(u,v,w)` 操作会删除 `u-v` 和 `u-w`，至多新增或删除 `v-w`，边数至少减少 1。",
                "重复后所有点度数都不超过 1，图只剩孤点和独立边。",
                "若没有边，已经是 cool 图。",
                "否则取一条边作当前树的基边；对孤点 w 操作 `(u,v,w)` 可把 w 接进当前结构并更新基边。",
                "对另一条独立边 `(a,b)` 操作 `(u,a,b)` 可把这条边合并进当前树。",
            ],
            "solution_brief": "关键观察：三角翻转先消高度数，再拼树。维护邻接集合；不断找度数至少 2 的点，把它连向两个邻居的边通过一次操作消掉。得到匹配后，若非空就选一条边为骨架，逐个用三角操作吸收孤点和其它边。操作数不超过 `m+n`，满足限制。",
            "primary_topic": "图论与网络流",
        },
        "2255A": {
            "statement_brief": "环上 `2n` 个位置按奇偶分两队，若某位置有物品，每轮可保留或向下一位传递，但下一位开局已有物品则不能传。双方合作博弈，问最优后两队得分。",
            "transformed_statement": "把题目先看成：每段连续 1 中只有最后一个 1 有移动机会，而且最优是在最后一轮才移动。",
            "key_observations": [
                "总分恒等于物品数量，因此一队得分增加会让另一队相对变差。",
                "连续 1 段内部的物品都被前方占用阻塞，只有段尾的 `10` 位置能移动。",
                "若段尾过早移动，会把下一次行动机会交给对方，对方可在后续轮抵消这次收益。",
                "因此段尾若要移动，应等到最后一轮，移动后对方没有反制机会。",
                "最终效果与 k 的具体大小无关：每个初始 `10` 在最后变成 `01`，其它 1 不动；全 1 环则无人能动。",
            ],
            "solution_brief": "关键观察：不要模拟 k 轮。若全环都是 1，按原位置奇偶计分；否则扫描每个位置 i：若 `s_i=1` 且 `s_{i+1}=0`，该物品最后会到下一队，给当前位置所属队得分；若 `s_i=s_{i+1}=1`，它不动，给另一队得分。按题意输出红蓝分数。",
            "primary_topic": "博弈",
        },
        "2252D": {
            "statement_brief": "数组中可选择内部位置 i，若两侧元素同奇偶，就把 `a_i` 变成 `a_{i-1}-a_i+a_{i+1}`。问能得到的字典序最小数组。",
            "transformed_statement": "把题目先看成：操作在差分数组上就是交换相邻两个同奇偶的差分值。",
            "key_observations": [
                "设 `d_i=a_{i+1}-a_i`。",
                "对位置 i 操作后，新的 `d_{i-1}` 等于旧 `d_i`，新的 `d_i` 等于旧 `d_{i-1}`。",
                "操作条件 `a_{i-1}` 与 `a_{i+1}` 同奇偶，等价于 `d_{i-1}+d_i` 为偶数，也就是两个差分同奇偶。",
                "因此差分数组中同奇偶的连续段可以任意相邻交换，最终可排序。",
                "要让原数组字典序最小，就把每个同奇偶差分段升序排列后从 `a_1` 重建。",
            ],
            "solution_brief": "关键观察：改值操作不是直接贪心改 a，而是在差分上排序。计算所有差分 d，按奇偶相同的最大连续段分组并分别升序排序；最后从原 `a_1` 开始依次累加排序后的差分，得到字典序最小数组。",
            "primary_topic": "构造与贪心",
        },
        "2245G": {
            "statement_brief": "交互题。隐藏一棵无向树。一次询问给一个点序列，交互器按序贪心返回其中一个独立集。总询问长度不超过 `30n`，要求找出所有边。",
            "transformed_statement": "把题目先看成：询问两个独立集 A、B 的拼接，可以识别 B 中哪些点与 A 至少有一条边。",
            "key_observations": [
                "任何询问返回的集合都是独立集。",
                "若 A、B 都是独立集，询问 `A+B` 时，A 会全部被选中；B 中未被选中的点正是与 A 有邻接的点。",
                "记这个集合为 `f(A,B)`；若已知 `B=f(A,B)`，就能用分治在 A 上找出 A 与 B 之间所有边。",
                "整体 DFS 时，先询问 T 得到独立集 S，再递归处理 `T\\S`；由于树的诱导子图是森林，可把 `T\\S` 二分成两个独立集。",
                "最后分别调用分治过程找 S 到两个独立集的跨边；摊还分析保证总询问长度小于 `30n`。",
            ],
            "solution_brief": "关键观察：交互返回的贪心独立集可以当成切分器。递归处理顶点集 T：询问 T 得到独立集 S，先求出 `T\\S` 内部边并二染色成两个独立集，再用 `find(S,W1)`、`find(S,W2)` 找跨边。`find` 把 A 对半分，查询每半连接到 B 的点集，并递归到单点时输出边。",
            "primary_topic": "交互",
        },
        "2245F": {
            "statement_brief": "给一个约束数组 a，要求统计有多少排列 p 经过题目中的单调栈过程后，输出数组 b 在所有 `a_i!=-1` 位置都等于 a。",
            "transformed_statement": "把题目先看成：一个区间的最小值会把单调栈过程切成左、右两个独立子问题。",
            "key_observations": [
                "在区间 `[l,r]` 中，若最小值在 k，它入栈时会弹掉左侧区间残留在栈里的所有元素。",
                "之后它作为栈底，不会被右侧任何元素弹出，因此左右区间可以独立计数。",
                "若 `a_k` 已知，则左区间处理完后栈中剩余元素个数必须等于 `a_k`；若未知则可为任意值。",
                "设 `f[l][r][c]` 表示区间处理后留下 c 个栈元素的方案数，枚举最小值位置 k 合并左右。",
                "再引入 `g[l][r]=sum_c f[l][r][c]`，可以在未知约束处减少需要维护的 c 维度。",
            ],
            "solution_brief": "关键观察：按区间最小值做 DP，而不是模拟所有排列。枚举 k 作为当前区间最小值，左侧贡献由 `a_k` 决定取某个 `f` 或总和 `g`，右侧贡献决定最终栈大小，再乘上左右相对值集合的组合数 `C(len,k-l)`。利用 `g` 和已知约束只保留必要的 c 状态，把复杂度压到可接受的 `O(n^3)`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2239A": {
            "statement_brief": "数组游戏中，每步要选择非零数组 b，满足 `0<=b_i<=a_i` 且所有 b 的异或为 0，然后把 a 减去 b。问先手第一步有多少种选择能保证获胜。",
            "transformed_statement": "把题目先看成：只要局面里至少两个数非零，当前玩家就能一步把局面变成至多一个非零数。",
            "key_observations": [
                "至多一个非零数时无法选出非零且异或为 0 的 b，是必败局面。",
                "若至少两个数非零，玩家可选择合适 b 把剩余数组压到至多一个非零数，从而获胜。",
                "设当前总异或为 X；若 X 为 0，唯一获胜选择是直接把所有数都减到 0。",
                "若 X 非零，选择让最后只剩第 i 个数，剩余值必须是 `a_i xor X`；可行条件是这个剩余值不超过 `a_i`。",
            ],
            "solution_brief": "关键观察：获胜第一步就是把对手送到“至多一个非零”的必败局。计算 `X=xor(a)`；若 X 为 0，答案为 1。否则统计满足 `(a_i xor X)<=a_i` 的下标数量，每个下标对应一种保留该位置、清空其它位置的获胜选择。",
            "primary_topic": "博弈",
        },
        "2238A": {
            "statement_brief": "数组 a 可任意次把元素减一，也可花 c 秒整体重排一次。要求变成数组 b，求最短时间或判无解。",
            "transformed_statement": "把题目先看成：减法总次数固定为 `sum(a)-sum(b)`，唯一决策是是否需要重排一次。",
            "key_observations": [
                "可行的充要条件是能把 a 重排到每个位置都不小于对应的 b。",
                "这个条件用排序后逐位比较即可检查。",
                "一旦可行，总减法次数始终是 `sum(a)-sum(b)`，与具体匹配方式无关。",
                "若原顺序已经逐位 `a_i>=b_i`，就不需要重排；否则必须支付一次重排费用 c。",
            ],
            "solution_brief": "关键观察：先判可行，再判是否要花重排费。排序 a、b，若存在排序后 `a_i<b_i` 则无解。否则令 `S=sum(a)-sum(b)`；若原数组逐位已满足 `a_i>=b_i`，答案为 S，否则答案为 `S+c`。",
            "primary_topic": "构造与贪心",
        },
        "2222C": {
            "statement_brief": "给奇数长度数组，要求把它分成尽量多的奇长连续段，且所有段的中位数相同。",
            "transformed_statement": "把题目先看成：所有段的共同中位数必须等于整个数组的中位数，然后做区间合法性 DP。",
            "key_observations": [
                "若每段中位数都是 x，把各段中小于、等于、大于 x 的数量相加，整个数组也会满足 x 是中位数的条件。",
                "因此共同中位数只能是原数组整体中位数。",
                "对固定 x，一个奇长区间的中位数为 x 当且仅当“小于等于 x 的数量大于大于 x 的数量”，且“大于等于 x 的数量大于小于 x 的数量”。",
                "于是可预处理或枚举区间判断其是否能作为一段。",
                "令 `dp[i]` 为前 i 个数最多分几段，从所有合法奇长区间 `[j+1,i]` 转移。",
            ],
            "solution_brief": "关键观察：先固定唯一可能的共同中位数。求整个数组中位数 x；然后按右端 i 枚举左端 j，只考虑奇长区间，并用计数判断 `[j+1,i]` 的中位数是否为 x。若合法，用 `dp[i]=max(dp[i],dp[j]+1)` 更新，答案是 `dp[n]`。",
            "primary_topic": "动态规划与状态设计",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2210A": {
            "statement_brief": "给定 n，构造一个 1 到 n 的排列，使相邻取模值从左到右单调不增。",
            "transformed_statement": "把题目先看成：只要让相邻取模结果变成一串相同值后接一个更小值即可。",
            "key_observations": [
                "倒序排列 `n,n-1,...,1` 会让大多数相邻对形如 `x mod (x-1)`。",
                "当 `x>2` 时，`x mod (x-1)=1`。",
                "最后一对是 `2 mod 1=0`。",
                "所以取模序列是若干个 1 后接 0，天然满足单调不增。",
            ],
            "solution_brief": "关键观察：倒序排列已经满足条件。直接输出 `n,n-1,...,1`，因为相邻取模结果为 `1,1,...,1,0`。",
            "primary_topic": "构造与贪心",
        },
        "2208C": {
            "statement_brief": "按顺序处理任务。完成第 i 个任务得当前体力乘 `c_i` 的分数，并让体力乘上保留比例；也可以跳过，求最大总分。",
            "transformed_statement": "把题目先看成：当前体力只是全局乘法因子，真正的后缀决策只依赖任务下标。",
            "key_observations": [
                "若把当前体力统一缩放，后续所有收益也会按同一比例缩放，最优选择不会改变。",
                "设 `f_i` 表示从第 i 个任务开始、当前体力为 1 时能获得的最大收益。",
                "跳过任务 i 得到 `f_{i+1}`。",
                "完成任务 i 得到 `c_i + (1-p_i/100)*f_{i+1}`。",
                "因此从后往前做一维转移即可。",
            ],
            "solution_brief": "关键观察：体力不需要作为状态。倒序维护 `ans` 表示当前后缀在体力为 1 时的最优收益，对每个任务更新为 `max(ans, c_i + (1-p_i/100)*ans)`，最后输出 `ans`。",
            "primary_topic": "动态规划与状态设计",
        },
        "2194C": {
            "statement_brief": "给 k 条长度为 n 的字符串，每个位置可从任意一条中选字符，要求构造最小周期尽量小的目标串。",
            "transformed_statement": "把题目先看成：枚举周期长度 d，并检查每个同余类的位置是否存在共同可选字母。",
            "key_observations": [
                "目标串周期为 d 时，所有位置 `i,i+d,i+2d,...` 必须选同一个字符。",
                "对每个原位置，先用 26 位集合表示该位置可选的字母。",
                "同一个同余类内把这些集合取交，若交集非空，就能为该类选一个字符。",
                "只需要枚举 n 的因子 d，并取第一个可行 d。",
                "题目约束下 n 的因子数很少，总复杂度可以写成 `O(26*n*d(n))`。",
            ],
            "solution_brief": "关键观察：最小信息度就是最小可行周期。枚举 n 的因子 d；对每个余数类求所有对应位置可选字母集合的交集，若全部非空，就按交集中任意字母构造长度 d 的周期节并重复到 n。",
            "primary_topic": "字符串",
        },
        "2194A": {
            "statement_brief": "n 块连续栅栏板中可拆若干块，但不能出现连续 w 块都被拆，求最多能拆多少块。",
            "transformed_statement": "把题目先看成：每连续 w 块里至少要保留一块。",
            "key_observations": [
                "若某段连续 w 块全被拆，割草机会从这个缺口离开。",
                "因此每 w 块至少保留一块，这是上界。",
                "按每 w 块保留第 w 块、其余拆掉可以达到这个上界。",
                "所以保留数量最少为 `floor(n/w)`，答案是 `n-floor(n/w)`。",
            ],
            "solution_brief": "关键观察：每 w 块留一块最优。直接输出 `n - floor(n/w)`。",
            "primary_topic": "构造与贪心",
        },
        "2189C2": {
            "statement_brief": "给定 n，要求构造长度 n 的排列 p，使每个 `1<=i<n` 都存在 `j>=i` 满足 `p_i = p_j xor i`；无解输出 -1。",
            "transformed_statement": "把题目先看成：先排除 n 为二的幂的无解情形，再在低位余数 r 上修补已有构造。",
            "key_observations": [
                "若 `n` 是二的幂，值 n 无论放在哪里都会导致某个需要的异或值超过 n，因此无解。",
                "若 n 不是二的幂，可写成 `n=2^x+r`。",
                "奇数 n 时，简版构造已经能满足 hard 版条件。",
                "偶数 n 时，在简版构造中交换 `p_1` 和 `p_r`。",
                "交换后只需额外检查位置 1 和 r：位置 1 用 `j=r+1`，位置 r 用 `2^x xor r=n` 对应的后续位置兜住。",
            ],
            "solution_brief": "关键观察：无解只发生在 n 为二的幂。否则沿用简版构造；若 n 为偶数且写成 `2^x+r`，交换构造中的第 1 位和第 r 位，再按题解证明检查被交换影响的位置即可。",
            "primary_topic": "构造与贪心",
        },
        "2187F1": {
            "statement_brief": "给两棵未知根树的 DFS 序，问是否存在共同树，并在存在时最大化共同树深度。",
            "transformed_statement": "把题目先看成：用其中一个 DFS 序重标号，把问题变成一个排列中哪些连续段能作为子树。",
            "key_observations": [
                "先按第二个 DFS 序的位置重标号，使它变成自然顺序。",
                "第一个 DFS 序变成排列 c；共同子树必须对应 c 的一个连续段。",
                "一个段合法的必要结构是：段首是该段最小值，且最大值减最小值等于段长减一。",
                "所有合法子树段会形成嵌套结构，不会任意交叉。",
                "分治求出每个起点的最大合法右端，再用栈模拟嵌套段即可得到最大深度。",
            ],
            "solution_brief": "关键观察：两棵树的共同 DFS 子树可转成排列上的合法连续段。重标号后分治计算每个起点能扩到的最远合法段，跨中点时按最大值在左或在右分别统计；最后按右端排序，用栈维护当前嵌套段数量，最大栈深加一就是答案。",
            "primary_topic": "树结构",
        },
        "2173E": {
            "statement_brief": "交互题。每次指定两个下标，交互器随机执行普通交换或镜像交换；要求在期望限制内把隐藏排列排好。",
            "transformed_statement": "把题目先看成：先把互补值放成中心对称，再在每个镜像组内用随机交换完成归位。",
            "key_observations": [
                "第一阶段处理每对值 `x` 和 `n+1-x`，让它们的位置关于中心对称。",
                "若两者不对称，询问 `pos[x]` 和 `mirror(pos[n+1-x])`，无论交互器选择哪种交换都会修好这一对。",
                "奇数 n 时，先把中间值放到中间位置。",
                "第二阶段按镜像组归位；一次询问有一半概率直接成功，失败时会落到另一个镜像组。",
                "对应期望满足 `T=1+1/2+1/2*(T+1)`，解得每组常数期望，总体约 `2.5n` 次询问。",
            ],
            "solution_brief": "关键观察：把随机镜像交换拆成确定修对称和期望归位两步。先遍历互补值对，保证位置成镜像；再逐组把当前值移到目标镜像组，若随机结果不是目标，就继续追踪被带到的组，期望次数仍在线性范围内。",
            "primary_topic": "交互",
        },
        "2147D": {
            "statement_brief": "数组游戏中，每次选一个正值 x，获得它的出现次数分，并把所有 x 都减成 x-1；双方最优，求最终得分。",
            "transformed_statement": "把题目先看成：偶数值会把同等或更好的机会交给对手，真正决定分差的是奇数值频率。",
            "key_observations": [
                "若选偶数 x，对手可以紧接着选 x-1，通常拿到不少于当前的收益。",
                "奇数值不同，因为选到 1 后不会再给对手留下 0 可选。",
                "把所有奇数值的出现次数降序为 `f_0,f_1,...`。",
                "先手最终分差等于交错和 `S=f_0-f_1+f_2-...`。",
                "总得分等于数组元素总和，因此 Alice 与 Bob 得分可由总和和分差还原。",
            ],
            "solution_brief": "关键观察：只统计奇数频率。计算数组和 `sum`，把每个奇数值的频率降序排列并求交错和 S；输出 Alice 为 `(sum+S)/2`，Bob 为 `(sum-S)/2`。",
            "primary_topic": "博弈",
        },
        "2146C": {
            "statement_brief": "构造一个排列，使值 i 被错误二分稳定找到当且仅当给定二进制串第 i 位为 1；无解时输出 -1。",
            "transformed_statement": "把题目先看成：值 x 稳定等价于它在正确位置，且左右两侧值域严格分开。",
            "key_observations": [
                "把小于 x、等于 x、大于 x 的元素分别看成 -1、0、1。",
                "错误二分要无论如何都找到 x，就要求这个三值数组在 0 左边全是 -1、右边全是 1。",
                "因此稳定的 x 必须满足 `p_x=x`，并且左侧全小于 x、右侧全大于 x。",
                "所有 `s_i=1` 的位置必须固定为 `p_i=i`。",
                "连续 0 段只能用自己的值域内部重排；若段长为 1，则该位置必然稳定，无法满足要求。",
            ],
            "solution_brief": "关键观察：1 位是固定点，0 段要整体打乱。若存在长度为 1 的连续 0 段，输出 -1；否则每段连续 0 内用循环移位或反转填入该段值域，让段内没有位置保持固定，所有 1 位填自身即可。",
            "primary_topic": "构造与贪心",
        },
        "2143A": {
            "statement_brief": "给一个排列，依次对长度 1 到 n 的子数组各减一一次，问能否最终全变成 0。",
            "transformed_statement": "把题目先看成：从最大值往下看，被大值集合占据的位置必须始终是一段连续区间。",
            "key_observations": [
                "值 n 需要被 n 次操作全部覆盖，所以每个被选子数组都必须包含它。",
                "值 n-1 只允许漏掉长度 1 的那次操作，因此必须和 n 相邻。",
                "继续往下推，集合 `{i,i+1,...,n}` 的位置必须始终构成连续段。",
                "反向等价于从小到大删除元素时，每次当前最小值都必须在剩余序列一端。",
                "也等价于原排列呈现先增后减的山形结构。",
            ],
            "solution_brief": "关键观察：连续段条件可以用双端删除检查。维护排列下标的双端区间，从值 1 到 n 依次看它的位置，若不在当前区间左端或右端则无解；否则删去对应端点，全部删完则可行。",
            "primary_topic": "构造与贪心",
        },
        "2136B": {
            "statement_brief": "给二进制串 s 和 k，构造排列，使每个 1 位置在任何长度至少 k 且覆盖它的区间内都不是最大值。",
            "transformed_statement": "把题目先看成：1 位置全部放小数，0 位置全部放大数；唯一障碍是存在长度 k 的全 1 区间。",
            "key_observations": [
                "若存在连续 k 个 1，那么这个区间的最大值必然落在某个 1 位置，条件不可能满足。",
                "若不存在连续 k 个 1，则每个长度至少 k 的区间都至少包含一个 0。",
                "把所有 1 位置填 `1..c`，所有 0 位置填 `c+1..n`。",
                "这样任意覆盖 1 位置的长区间里都有一个 0，且它的值大于所有 1 位置。",
            ],
            "solution_brief": "关键观察：先判连续 1 长度。若最大连续 1 长度达到 k，输出 NO；否则输出 YES，并把 1 位按顺序填小数、0 位按顺序填大数。",
            "primary_topic": "构造与贪心",
        },
        "2134D": {
            "statement_brief": "给一棵树，一次 sliding 操作会把某个中心点除两条指定边外的邻边搬到另一个邻点上；要求最少操作变成一条路径，并输出第一步。",
            "transformed_statement": "把题目先看成：每次操作至多让树直径增加 1，而路径图的直径必须是 n-1。",
            "key_observations": [
                "任意一次 sliding 操作对任意两点间距离的增加量最多为 1。",
                "因此直径也最多增加 1，答案下界是 `n-1-diameter`。",
                "若树已经是路径，直接输出 -1。",
                "否则取一条直径路径，必存在某个直径点连着非直径子树。",
                "把这个非直径分支沿直径方向滑动，可以让直径恰好增加 1，从而达到下界。",
            ],
            "solution_brief": "关键观察：最优步数由直径缺口决定。求一条直径并标记其点；找到直径上一点 u 及其非直径邻点 v，令 a 为 u 在直径上朝某个端点的相邻点，输出操作 `(a,u,v)`。这一步会把直径增长 1，反复执行即可最优；题目只要求输出第一步。",
            "primary_topic": "树结构",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2092A": {
            "statement_brief": "给若干只羊的不同美丽值。可以先给所有羊统一加上同一个非负整数 d，再选两只羊，最大化这两只羊新美丽值的最大公约数。",
            "transformed_statement": "把题目先看成：统一加 d 不改变两数差值，而两数的最大公约数永远不能超过它们的差。",
            "key_observations": [
                "对任意 `x<y`，有 `gcd(x+d,y+d)` 整除 `(y+d)-(x+d)=y-x`。",
                "所以任意一对羊带来的快乐值最多是它们原始美丽值之差。",
                "取全局最小值 x 和最大值 y，差值最大。",
                "选择 `d ≡ -x (mod y-x)`，可让 `x+d` 和 `y+d` 同时被 `y-x` 整除。",
                "因此最大快乐值就是 `max(a)-min(a)`。",
            ],
            "solution_brief": "关键观察：统一加 d 只能让一对数的 gcd 达到它们的差，不能超过差。最大差来自数组最大值和最小值，并且可通过合适的 d 达到，所以直接输出 `max(a)-min(a)`。",
            "primary_topic": "数论与同余",
        },
        "2053G": {
            "statement_brief": "给目标串 t 和查询串 s。对 s 的每个切分点，把前缀和后缀作为两个候选块，判断 t 是否能完全拆成这两种块的拼接。",
            "transformed_statement": "把题目先看成：短块优先贪心匹配；贪心失败时，只需处理长块相对短块的周期错位和少量回退。",
            "key_observations": [
                "令较短的块为 `s1`、较长的块为 `s2`；块顺序交换不影响能否拆分。",
                "直接贪心先放尽量多的短块，再尝试放长块；真正会出错的情况来自长块可看成若干短块加一个尾巴。",
                "若多回退一些短块会改变可行性，本质上要求短块、长块和尾巴共享同一个周期。",
                "因此先检查共同周期，把复杂的回退情况压成一个线性方程 `x*|s1|+y*|s2|=|t|`。",
                "线性优化时，每次尝试长块前只需回退 `c` 或 `c+1` 个短块，其中 c 是长块前缀能覆盖的短块数。",
            ],
            "solution_brief": "关键观察：这题不是上后缀结构，而是修正“短块贪心”的唯一漏洞。对每个切分点，把短块连续匹配到不能匹配；放长块前只检查两种回退量，并用周期性判断尾巴能否接上。配合批量跳过连续短块匹配，所有切分点总复杂度可压到线性量级。",
            "primary_topic": "字符串",
        },
        "2040D": {
            "statement_brief": "给一棵树，要给每个点分配 1 到 2n 中互不相同的数，使每条边两端差的绝对值都不是质数。",
            "transformed_statement": "把题目先看成：只要让每条树边跨越的数差大多是大于 2 的偶数，最后少量冲突用叶子修补。",
            "key_observations": [
                "大于 2 的偶数一定不是质数，因此构造目标是让相邻点差变成这种数。",
                "一种做法按深度奇偶分组：偶深点填较小偶数，奇深点填较大偶数。",
                "树边必然连接奇偶深度，差值通常是偶数且较大。",
                "若唯一可能冲突出现在某个叶子和父亲之间，可把叶子值改成父亲值减 1 来修补。",
                "题解也给出 DFS 顺序递增并按冲突跳数的构造，本质同样是在避开奇质数和差值 2。",
            ],
            "solution_brief": "关键观察：树是二分的，边只连相邻深度。按深度奇偶把点分到两侧，一侧填递增偶数，另一侧填从 `2n` 往下的偶数；绝大多数边差都是合格偶数。检查若只剩叶子冲突，则用父亲值附近的未用数替换叶子，得到合法标号。",
            "primary_topic": "树结构",
        },
        "2039F2": {
            "statement_brief": "统计所有元素不超过 m、长度任意的非空 good 数组；good 指不同子数组长度对应的“所有该长度子数组最大值的 gcd”两两不同。",
            "transformed_statement": "把题目先看成：只统计严格递增骨架，并把状态从长度改成每个位置开始的后缀 gcd。",
            "key_observations": [
                "困难版不能再把长度放进状态，需要从小到大枚举当前元素值。",
                "构造严格递增序列时，固定最终数组中从元素 j 开始的后缀 gcd 为 h。",
                "状态 `dp[j,h]` 汇总当前已构造序列的权值 `2^{len-1}`。",
                "从前一个元素 i 转移到 j 时，需要旧后缀 gcd `g` 满足 `g|h`、`g<h` 且 `g=gcd(i,h)`。",
                "转移求和可在 i 的因子上做容斥或 divisor SOS，避免逐个枚举所有前驱。",
            ],
            "solution_brief": "关键观察：把数组长度从 DP 状态里拿掉，改用“当前值 j + 后缀 gcd h”描述未来 f(k) 的变化。枚举 j 和 h 时，用因子关系筛出能转来的 `(i,g)`；对这些条件在约数集合上做莫比乌斯容斥或 SOS 汇总，得到可承受的总复杂度。",
            "primary_topic": "数论与同余",
        },
        "2030D": {
            "statement_brief": "给排列 p 和由 L/R 组成的操作权限串 s。每次可按权限交换相邻元素，多次查询会翻转一个字符，问当前是否能把排列排序。",
            "transformed_statement": "把题目先看成：每个值 i 必须能从当前位置移动到目标位置 i；不能跨过模式 `LR` 形成的阻断边界。",
            "key_observations": [
                "若要把位置 i 的元素移到位置 j，中间不能存在 `s_k=L` 且 `s_{k+1}=R` 的边界。",
                "对每个值 v，它需要覆盖区间 `[min(pos[v],v), max(pos[v],v))` 中的所有边界。",
                "用差分数组统计每条边界被多少个值的需求区间覆盖。",
                "只有被覆盖次数大于 0 的边界才重要。",
                "一次翻转 `s_i` 只会影响边界 `i-1` 和 `i` 是否从好变坏或从坏变好。",
            ],
            "solution_brief": "关键观察：排序可行性只取决于“被需要跨越的边界里有没有 LR 阻断”。预处理每条相邻边是否被某个元素的目标移动区间覆盖；维护所有同时满足“被覆盖且是 LR”的坏边界。每次修改只重新检查相邻两个边界，坏集合为空则输出 YES。",
            "primary_topic": "数据结构",
        },
        "2027D1": {
            "statement_brief": "给数组 a 和递减数组 b。当前参数 k 可免费增大；也可付费删除当前数组一个前缀，前缀和不能超过 `b_k`，费用为 `m-k`。求删空 a 的最小费用。",
            "transformed_statement": "把题目先看成：状态是已经删掉多少前缀和当前 k；付一次固定费用时，应该尽量删到最远。",
            "key_observations": [
                "令 `dp[i][j]` 表示删掉前 i 个元素、当前 `k=j` 的最小费用。",
                "免费操作只是从 `dp[i][j]` 转移到 `dp[i][j+1]`。",
                "付费删除时费用只由 j 决定，和这次删多少无关。",
                "因此在同一个状态下，只需要删到满足前缀和限制的最远位置 r。",
                "每个 j 固定时，所有 i 对应的最远 r 可以用前缀和二分，也可以双指针维护。",
            ],
            "solution_brief": "关键观察：付费一次就应该尽量多删。预处理或在线求 `nxt[i][j]`，表示从 i 后开始在 `b_j` 限制下最多能删到哪里；DP 中同时做免费增大 k 和付费跳到 `nxt[i][j]`，最后取所有 `dp[n][j]` 的最小值。",
            "primary_topic": "动态规划与状态设计",
        },
        "2021E2": {
            "statement_brief": "给一个带权连通图和若干需要联网的房屋。最多安装 k 个服务器，每个需求房屋连接到某个服务器的代价是路径上最大边权；对每个 k 求最小总代价。",
            "transformed_statement": "把题目先看成：在图上选择服务器集合，使所有指定点到最近服务器的瓶颈距离之和最小；本地缺少题解正文，暂不提炼关键观察。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留题面、原题链接和题解链接，避免根据旧总结或宽标签补写。",
            "extraction_status": "missing_editorial",
            "primary_topic": "图论与网络流",
        },
        "2021E1": {
            "statement_brief": "给一个带权连通图和若干需要联网的房屋。最多安装 k 个服务器，每个需求房屋连接到某个服务器的代价是路径上最大边权；对每个 k 求最小总代价。",
            "transformed_statement": "把题目先看成：在图上选择服务器集合，使所有指定点到最近服务器的瓶颈距离之和最小；本地缺少题解正文，暂不提炼关键观察。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留题面、原题链接和题解链接，避免根据旧总结或宽标签补写。",
            "extraction_status": "missing_editorial",
            "primary_topic": "图论与网络流",
        },
        "2021B": {
            "statement_brief": "给数组 a 和整数 x。一次操作可把某个元素加 x，操作次数不限，求最终能得到的最大 MEX。",
            "transformed_statement": "把题目先看成：一个数只能沿着同余类向上移动，所以重复的小值可以被推给同余的后续缺口。",
            "key_observations": [
                "MEX 至多为 n，因为数组只有 n 个元素。",
                "大于 n 的初始值不可能帮助补齐 `0..n` 内的缺口，可以忽略。",
                "扫描 k 时，如果 `freq[k]>0`，保留一个 k 用来覆盖当前值。",
                "多余的 k 可以通过加 x 变成 `k+x`，所以把 `freq[k]-1` 累加到 `freq[k+x]`。",
                "遇到第一个 `freq[k]=0` 的 k，就是最大 MEX。",
            ],
            "solution_brief": "关键观察：按值从小到大“搬运多余频次”。先统计 `0..n` 范围内频率；从 0 扫到 n，若当前位置为空就停止，否则保留一个，并把多余元素推到 `k+x`。这种贪心不会损失，因为小值必须先被覆盖。",
            "primary_topic": "数论与同余",
        },
        "2249E2": {
            "statement_brief": "定义无限 k 进制数字串 s，其中第 i 位是 i 的 k 进制数位和模 k。每次给区间和模式串 t，求 t 在该区间中出现多少次。",
            "transformed_statement": "把题目先看成：无限串按长度 k 分块后，每块都是 `0..k-1` 的循环位移；压缩块位移后又得到同一个无限串。",
            "key_observations": [
                "每个长度 k 的完整块都是 `012...(k-1)` 的某个循环位移。",
                "把每个完整块替换成它的位移值，得到的高层序列仍然是原来的 s。",
                "对模式串看相邻差分 `d_i=(t_i-t_{i-1}+k) mod k`，块内差分恒为 1。",
                "所有 `d_i!=1` 的位置必须对应同一种块边界，即它们模 k 的余数必须相同。",
                "若边界被确定，就把模式串和查询区间同时按块压缩并递归；若全是 1，则出现长度不会超过 `2k`，枚举对齐后转成长度 1 或 2 的计数。",
            ],
            "solution_brief": "关键观察：这是自相似字符串计数。先用差分判断模式是否能对齐到块边界；若能，就删掉两端不完整块，把整块压成位移值后递归。若差分全为 1，则只需枚举有限个块内对齐，最后落到单字符或双字符出现次数；双字符次数用按 k 进制层级预处理的前缀计数回答。",
            "primary_topic": "字符串",
        },
        "2248D": {
            "statement_brief": "给两个二进制串，多次询问区间。判断这两个区间子串能否通过若干次同步删除同一组位置并满足众数条件，最终同时删空。",
            "transformed_statement": "把题目先看成：每个位置只看二元列类型 `(s_i,t_i)`，好坏由四类列的数量关系决定。",
            "key_observations": [
                "设混合列数量为 `x=N(0,1)`、`y=N(1,0)`，纯列数量为 `u=N(0,0)`、`v=N(1,1)`。",
                "每次合法删除中，混合列差值的绝对变化不能超过同时删掉的纯列数。",
                "定义势能 `|x-y|-(u+v)`，删除操作不会让它变小，而空串时势能为 0。",
                "因此必要条件是 `|x-y|<=u+v`。",
                "充分性也成立：先把 `(0,1)` 和 `(1,0)` 配对删除，剩余混合列用纯列配掉，最后纯列可成对或单独删除。",
            ],
            "solution_brief": "关键观察：区间是否 good 只需四类列计数。预处理 `(0,0),(0,1),(1,0),(1,1)` 的前缀和；每个询问取出 `u,v,x,y`，判断 `abs(x-y)<=u+v` 即可。",
            "primary_topic": "构造与贪心",
        },
        "2248B": {
            "statement_brief": "给两个互不相交且元素互异的数组 a、b。可反复把 a 中两个数合并成介于二者之间的任意数，最后重排，问能否得到 b。",
            "transformed_statement": "把题目先看成：每个最终的 b 值必须由 a 的一组原数合并而来，并且该组最小值和最大值要夹住它。",
            "key_observations": [
                "每次合并都会让 a 的元素个数减一；因为 a、b 元素互异，最终每个 b 都不能只来自一个原元素。",
                "所以必要条件之一是 `n>=2m`。",
                "排序后，第 i 小的 b 至少要大于等于第 i 小的 a，否则左侧原数不够分给前 i 个组。",
                "对称地，第 i 小的 b 至多为 `a_{n-m+i}`，否则右侧也不够。",
                "若这些条件成立，可把 `a_i` 和 `a_{n-m+i}` 配成一组并合并为 `b_i`，中间剩余元素再逐个吸收到任意组里。",
            ],
            "solution_brief": "关键观察：排序后只检查夹逼条件。若 `n<2m`，必然无解；否则排序 a、b，逐个检查 `a_i<=b_i<=a_{n-m+i}`。全部满足时，端点配对已经能生成每个 b，中间多余元素不会破坏可行性。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2215F": {
            "statement_brief": "一副牌有一张绿牌和若干白牌，双方轮流从牌顶取至多 k 张，可丢一张并把其余放回底部；Alice 想最大化绿牌被她丢掉时的分数，Bob 想最小化。",
            "transformed_statement": "把题目先看成：只需跟踪绿牌下一次浮到顶部前，牌堆大小会如何在双方选择下变化。",
            "key_observations": [
                "游戏不会无限进行，因为 Bob 可以持续删白牌压小牌堆，并在必要时迫使绿牌结束。",
                "当绿牌在顶端且 `n≡k (mod 2k)` 时，Alice 无论怎么放回都拿不到下一次先手，直接丢掉最优。",
                "否则 Alice 可以通过把绿牌放在取出牌的前面或后面，保证下一次仍由自己拿到绿牌。",
                "设 `x=floor((n+k)/(2k))`，一轮回到 Alice 拿绿牌前大约会减少 x 张牌。",
                "双方是否额外删牌可看成在 `n-x-1,n-x,n-x+1` 三个后继状态中做极大极小选择，得到记忆化递推。",
            ],
            "solution_brief": "关键观察：把整局压成 `f_k(n)`，表示绿牌在顶端且由 Alice 行动时的最优分数。根据 `n mod 2k` 分类：直接结束、只能向一侧转移，或在三个相邻后继状态上做 min/max。初始 `s` 不为 1 时先模拟绿牌浮到顶部前的完整轮数，再落到同一个 `f_k` 递推。",
            "primary_topic": "博弈",
        },
        "2192E": {
            "statement_brief": "给两个长度相同的数组 a、b。每个位置最多交换一次 `a_i` 和 `b_i`，问能否让最终 a 成为最终 b 的一个重排，并输出操作位置。",
            "transformed_statement": "把题目先看成：每个位置是一条连接 `a_i` 与 `b_i` 的边，交换就是翻转这条边方向；目标是让每个值入度等于出度。",
            "key_observations": [
                "最终 a、b 频率相同，等价于每个值作为边起点和终点的次数相同。",
                "若某个值在 a、b 合起来出现奇数次，则无论怎么翻边都不可能平衡。",
                "把每对 `(a_i,b_i)` 看成无向边后，每个点总度数必须为偶数。",
                "偶度无向图可分解成欧拉回路；沿欧拉回路定向后，每个点入度等于出度。",
                "某条边定向与原方向相反，就在对应下标执行交换。",
            ],
            "solution_brief": "关键观察：数组问题等价于欧拉图定向。先检查所有值总出现次数是否为偶数；若是，对每个连通块找欧拉回路，并按回路方向给边定向。与原 `a_i->b_i` 方向相反的边就是需要交换的位置。",
            "primary_topic": "图论与网络流",
        },
        "2190C": {
            "statement_brief": "交互题。隐藏排列 p，要求找到字典序最小的排列 q，使 `q>p` 且反转后也大于 `rev(p)`；只需输出 q 中元素来自 p 的下标顺序。",
            "transformed_statement": "把题目先看成：选择一个子数组重排，并要求这个子数组的左右端点都被变大。",
            "key_observations": [
                "`q>p` 和 `rev(q)>rev(p)` 等价于：第一次不同的位置 i 变大，最后一次不同的位置 j 也变大。",
                "固定子数组 `[i,j]` 后，若 `p_i` 或 `p_j` 是该段最大值，就无法同时让两个端点变大。",
                "合法时，为了字典序最小，应把段内大于 `p_i` 的最小值放到 i，剩余元素升序排列。",
                "最优 i 是最后一个局部最大值 k 的前一位，即 `i=k-1`；若没有局部最大值则无解。",
                "`[k,n]` 先降后升，后续排序可用三段单调指针和比较询问在 `3n` 次内完成。",
            ],
            "solution_brief": "关键观察：双向字典序条件只约束重排段的两个端点。先用相邻比较找最后一个局部最大值 k，取 `i=k-1`；然后把后缀拆成已知的三段单调序列，用询问归并得到升序顺序，并把刚好大于 `p_i` 的元素提到段首，其余按升序放回。",
            "primary_topic": "交互",
        },
        "2183D1": {
            "statement_brief": "根树初始全白。一次可选若干白点染黑，但选中点不能同深度，也不能相邻；简单版只求最少操作数。",
            "transformed_statement": "把题目先看成：每次操作像给点染一种时间颜色，同深度点和父子点不能同色。",
            "key_observations": [
                "同一深度的点不能同一次染黑，因此答案至少是最大层宽。",
                "若某层的一批点共享父亲，那么这些点分属不同操作，它们的父亲还必须避开这些操作。",
                "所以还要考虑“某个父亲的孩子数加一”的下界。",
                "题解说明这个下界可以由 困难版构造达到。",
                "因此 简单版答案就是这些下界的最大值。",
            ],
            "solution_brief": "关键观察：不用真的构造集合，只算冲突下界。统计每个深度的点数，以及每个点的孩子数；答案取 `max(最大层宽, 最大孩子数+1)`，对应同层互斥和父子互斥两类瓶颈。",
            "primary_topic": "树结构",
        },
        "2176F": {
            "statement_brief": "给数组 a 和 k，要求对所有下标对求 `omega(a_i*a_j)^k` 之和，其中 omega 表示不同质因子个数。",
            "transformed_statement": "把题目先看成：按 gcd 精确值和两数 omega 之和分组计数，再把乘积的 omega 拆出来。",
            "key_observations": [
                "`omega(x*y)=omega(x)+omega(y)-omega(gcd(x,y))`。",
                "在题目值域下，一个数的不同质因子个数很小，最大约为 6。",
                "令 `cnt[g][len]` 表示数组中能被 g 整除且 omega 等于 len 的数的数量。",
                "先用倍数枚举得到 cnt，再从大到小做容斥，得到 gcd 恰好为 g、omega 和为 s 的配对数 `dp[g][s]`。",
                "每个分组对答案贡献 `dp[g][s]*(s-omega(g))^k`。",
            ],
            "solution_brief": "关键观察：把乘积的不同质因子数转成“两个数的 omega 和减去 gcd 的 omega”。预处理每个值的 omega，按倍数统计 `cnt[g][len]`；再枚举 g 的倍数，把 gcd 为更大倍数的配对扣掉，得到精确 gcd 分组并累加幂次贡献。",
            "primary_topic": "数论与同余",
        },
        "2158A": {
            "statement_brief": "已知一场比赛发出了 y 张黄牌和 r 张红牌。红牌或两张黄牌都会让一名玩家停赛，求最多能有多少名玩家停赛。",
            "transformed_statement": "把题目先看成：红牌一张换一个停赛名额，黄牌两张换一个停赛名额，总数再受玩家人数限制。",
            "key_observations": [
                "一张红牌即可让一个玩家停赛，因此红牌应尽量给不同玩家。",
                "两张黄牌才能让一个玩家停赛，因此黄牌最多贡献 `floor(y/2)` 个停赛名额。",
                "多余的牌可以发给已经停赛的人对应的过程里，不会增加人数。",
                "最终停赛人数不能超过总玩家数 n。",
            ],
            "solution_brief": "关键观察：每个停赛名额的最低用牌成本独立。答案直接是 `min(n, r + floor(y/2))`。",
            "primary_topic": "基础实现与模拟",
        },
        "2152D": {
            "statement_brief": "数组游戏中，Poby 每次把一个数除以 2 下取整，Rekkles 每次把一个数加 1；直到全为 1。对多次区间询问求双方最优下 Poby 的操作次数。",
            "transformed_statement": "把题目先看成：单个数在对手干扰下等价于反复做 `floor((x+1)/2)`，再按初值是否为 `2^k` 或 `2^k+1` 分类。",
            "key_observations": [
                "单数反复执行 `x -> floor((x+1)/2)`，到 1 的步数是 `floor(log2 x)` 或再加 1。",
                "把初值分为 A 类 `2^k`、B 类 `2^k+1`、C 类其它数。",
                "A 类贡献 `floor(log2 x)`，C 类贡献 `floor(log2 x)+1`。",
                "B 类取决于谁先碰到它；双方镜像策略会让至多一半 B 类被 Rekkles 抢先变成加一贡献。",
                "所以区间答案为 `sum floor(log2 a_i)+floor(count_B/2)+count_C`。",
            ],
            "solution_brief": "关键观察：对每个数只需预处理基础 log 贡献、是否为 `2^k+1`、是否为其它 C 类。区间询问用前缀和拿到三项：log 和、B 类数量、C 类数量，套公式 `logSum + floor(B/2) + C`。",
            "primary_topic": "博弈",
        },
        "2139B": {
            "statement_brief": "有 n 个烤箱，第 i 个每秒产 `a_i` 个蛋糕。每秒末可以去一个烤箱收走其累计蛋糕，m 秒内最大化总收获。",
            "transformed_statement": "把题目先看成：每个烤箱的贡献只取决于最后一次被访问的时刻，最优策略只在最后若干秒访问不同烤箱。",
            "key_observations": [
                "同一个烤箱多次访问时，只有最后一次前累积的蛋糕真正重要。",
                "最多只有 `min(n,m)` 个烤箱值得在最后 `min(n,m)` 秒分别访问。",
                "倒过来看，最后一秒访问的烤箱乘数最大，倒数第二秒次之。",
                "产速越大的烤箱应分配越大的剩余秒数乘数。",
                "因此把 a 降序排序后按 `m,m-1,...` 加权求和。",
            ],
            "solution_brief": "关键观察：排序匹配乘数。将 `a` 降序排列，答案为 `sum a_i * max(0, m-i+1)`，也就是让产速最高的烤箱最晚收。",
            "primary_topic": "构造与贪心",
        },
        "2134E": {
            "statement_brief": "交互题。每个盒子的隐藏值为 1 或 2。可以相邻交换盒子，也可以向某位置投球并观察跳出前跳了几次，要求在 `ceil(3n/2)` 次询问内确定所有值。",
            "transformed_statement": "把题目先看成：先用每个位置投球得到跳数差分；跳数相邻关系能直接判定大部分位置，剩下未知位置不会相邻。",
            "key_observations": [
                "令 `d_i` 为从位置 i 投球的跳数，并设 `d_{n+1}=d_{n+2}=0`。",
                "若 `d_{i+1}!=d_{i+2}`，则可由 `d_i` 与 `d_{i+1}+1` 的关系判断 `a_i` 是 1 还是 2。",
                "若 `d_{i+1}=d_{i+2}`，当前位置 i 暂时未知，但此时可直接推出 `d_i=d_{i+1}+1`，省下一次投球。",
                "未知位置不可能相邻，因为 i 未知会导致 `d_i!=d_{i+1}`，从而 i-1 已知。",
                "对每个未知 i，和相邻已知位置交换后再投一次，就能反推出原来的 `a_i`。",
            ],
            "solution_brief": "关键观察：未知点稀疏到最多一半。先从右往左处理跳数，能判定就投球，不能判定就标记未知并省询问；随后每个未知点用一次相邻交换加一次投球恢复其值。由于未知点不相邻，总询问数不超过 `ceil(3n/2)`。",
            "primary_topic": "交互",
        },
        "2107F1": {
            "statement_brief": "一排骑车人有敏捷值。Leo 可以花费超越当前前方的人，也可通过交换调整顺序，求超过所有人的最小代价；简单版只求整段答案。",
            "transformed_statement": "把题目先看成：每个后缀先找最小敏捷值，用它通过交换来承担一段连续超越，然后递归处理剩余后缀。",
            "key_observations": [
                "对当前后缀 `[i,n]`，设 p 是最小敏捷值所在位置。",
                "用 p 的敏捷值去超越 p 之前的人不劣，因为这些人的敏捷值都更大。",
                "若想把 p 用到更靠后的 q，也可以通过交换把 p 带过去，不需要借用前缀其它值。",
                "所以选择一个分割点 j，让 p 负责 `[i,j]`，剩下 `[j+1,n]` 独立成为子问题。",
                "转移代价为超越次数乘 `a_p`，加上把 p 移到相应位置所需的交换次数。",
            ],
            "solution_brief": "关键观察：最小值是当前后缀的“工具人”。令 `dp[i]` 为处理后缀 `[i,n]` 的最小代价；找到该后缀最小值位置 p，枚举 p 负责到的终点 j，转移 `dp[i]=min(dp[j+1]+a_p*(j-i+1)+交换代价)`，简单版 `O(n^2)` 可过。",
            "primary_topic": "动态规划与状态设计",
        },
        "2063D": {
            "statement_brief": "平面上有两条水平线上的若干点。每次选三点成非共线三角形并删除，得分为面积；对每个操作次数 k，求恰好 k 次的最大得分。",
            "transformed_statement": "把题目先看成：一次三角形只会从某一条水平线上选两个点，贡献就是这两个点横坐标差。",
            "key_observations": [
                "若一次操作在下方线选两点，贡献为排序后左右端点差；上方线同理。",
                "做 p 次下方双点操作、q 次上方双点操作时，最优就是每条线分别取最外侧点配对，贡献可由前缀和表示。",
                "恰好 k 次时令 `q=k-p`，可行条件化为 `max(0,2k-m)<=p<=min(k,n-k)`。",
                "目标函数 `g(p,k-p)` 是两段严格递减差值前缀和的组合，关于 p 呈单峰/凸性结构。",
                "因此每个 k 只需在可行 p 区间上三分或用双指针找最优。",
            ],
            "solution_brief": "关键观察：几何面积退化成两条线上端点差的选择。先排序 a、b，预处理从两端取点的差值前缀和；对每个 k 求 p 的可行区间，再最大化 `prefA[p]+prefB[k-p]`。利用函数单峰性做整数三分即可。",
            "primary_topic": "几何",
        },
        "2028E": {
            "statement_brief": "树上 Alice 从任意起点出发，根为出口，非根叶子为失败点。每分钟公平硬币决定 Alice 或 Queen 移动一步，双方最优，求每个起点成功逃出的概率。",
            "transformed_statement": "把题目先看成：Alice 永远朝根走，Queen 永远朝最近叶子压；局面沿若干条最短根叶路径分解。",
            "key_observations": [
                "沿任意叶到根路径，越靠近根 Alice 逃脱概率越高，所以 Alice 最优是向父亲走。",
                "Queen 的最优反制是向当前子树中最近的叶子走。",
                "令 `d(v)` 为 v 子树内到最近叶子的距离，`t(v)` 为从 v 逃脱概率。",
                "题解给出递推 `t(v)=d(v)/(d(v)+1)*t(parent(v))`。",
                "可把树拆成若干条最短根叶路径，沿路径用上述递推向下传概率。",
            ],
            "solution_brief": "关键观察：双方最优方向固定后，概率只剩最近叶距离。一次 DFS 求每个点子树内最近叶距离 d，再从根向下转移：根概率为 1，非根 `ans[v]=ans[parent]*d(v)/(d(v)+1)`，按模数用逆元输出。",
            "primary_topic": "树结构",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2018A": {
            "statement_brief": "有 n 种牌，第 i 种已有 a_i 张，可再买最多 k 张。买完后要把所有牌分成若干等大小牌组，同组不能有重复牌值，求最大牌组大小。",
            "transformed_statement": "把题目先看成：枚举目标牌组大小 s，判断是否能把总牌数补成 s 的倍数，并保证每种牌不超过牌组数。",
            "key_observations": [
                "牌组大小最多是 n，因为一个牌组内每种牌最多出现一次。",
                "若总牌数为 m 且不再买牌，大小 s 可行当且仅当 m 是 s 的倍数，并且最大频次 x 不超过牌组数 m/s。",
                "充分性不是显然贪心：每次拿当前频次最高的 s 种牌组成一组，条件会在删除后继续成立。",
                "若答案不能做到 n，就不需要增加最大频次 x；买牌只是在固定 x 的约束下补总数。",
                "因此对每个 s，只需检查能否补到 x*s，或者在总数已经超过 x*s 时补到下一个 s 的倍数。",
            ],
            "solution_brief": "关键观察：分组可行性完全由“总数整除”和“最大频次不超过牌组数”刻画。先算总牌数 m 和最大频次 x；从大到小尝试 s，若能用不超过 k 张牌把总数变为至少 m、且是 s 的倍数并不少于 x*s，则 s 可行。答案为最大的可行 s。",
            "primary_topic": "构造与贪心",
        },
        "2255B": {
            "statement_brief": "给一个二进制串。一次操作可选择当前首尾字符相同的一段并反转，求能得到多少个不同二进制串。",
            "transformed_statement": "把题目先看成：操作只是在不改变首字符、0/1 总数和两种颜色 run 数的前提下，重新分配各 run 的长度。",
            "key_observations": [
                "反转段的两个端点字符相同，所以边界颜色不变；首字符、两种字符总数、0-run 数和 1-run 数都是不变量。",
                "首字符和两种 run 数确定了整串 run 的颜色顺序。",
                "反过来，形如 x^a y^b x^c 的三段结构中，可以选两个 x-run 内的端点反转，从而在两个 x-run 间任意重新分配总长度。",
                "重复这种局部调整后，每种颜色的 run 长度可以变成任意正整数拆分，且两种颜色互不影响。",
                "所以答案只剩组合数：把 cnt0 个 0 分成 seg0 段、cnt1 个 1 分成 seg1 段。",
            ],
            "solution_brief": "关键观察：可达状态不是按操作搜索，而是由 run 不变量和可重分配性刻画。统计 0/1 数量和 run 数，答案为 C(cnt0-1, seg0-1) * C(cnt1-1, seg1-1)，某种字符不存在时该因子按 1 处理。",
            "primary_topic": "组合计数与概率",
        },
        "2229D": {
            "statement_brief": "给两行数组，每次合并相邻两列的四个数，删去最小和最大，只保留中间两个。做 n-1 次后最大化最后两数的较小值。",
            "transformed_statement": "把题目先看成：二分答案 m，把大于等于 m 的数记为 1，其余记为 0；只需判断最终能否得到两个 1。",
            "key_observations": [
                "阈值化后，操作等价于在四个二进制数里删除最小和最大。",
                "令 diff=1 的数量减 0 的数量；除非四个数全 0 或全 1，否则删掉一个 0 和一个 1，diff 不变。",
                "全 0 合并会让 diff 增加 2，全 1 合并会让 diff 减少 2，因此目标是尽量制造全 0 合并、避免全 1 合并。",
                "没有 (1,1) 列的连续段内，可以任意合并，并尽可能把其中的 (0,0) 利用掉来提高 diff。",
                "当所有这样的段处理完后，若 diff 为正，就可以继续合并而不把优势耗尽，最终两个数都为 1。",
            ],
            "solution_brief": "关键观察：原值大小只通过阈值 m 影响 0/1 分类。对 m 二分；每次扫描列类型，在不含双 1 列的段内做贪心压缩并更新 diff，最后检查 diff 是否为正。最高可行 m 就是答案。",
            "primary_topic": "构造与贪心",
        },
        "2211H": {
            "statement_brief": "给一个排列。可以反复选择长度 3 的连续段并删除其中中位数；对每个位置 i，求仍保留 p_i 时可达到的最小数组长度。",
            "transformed_statement": "把题目先看成：任意一段最终都能缩成该段最小值和最大值，所以每个目标元素只需判断能否被少数极值保护到长度 3、4 或 5。",
            "key_observations": [
                "固定子数组可以被缩成两个元素：该段的最小值和最大值；这让答案整体最多为 5。",
                "判断答案是否不超过 4 时，只需看 i 左侧的前缀最小/最大位置和右侧的后缀最小/最大位置。",
                "设 l 为左侧两个极值位置较靠右者，r 为右侧两个极值位置较靠左者；若 [l,r] 内有一个值跳出 p_l、p_r 的夹区间，就能删掉阻碍极值。",
                "判断答案是否为 3 还要考虑全局 1、n 与 p_i 的相对位置，因为最终三元组通常要由 1、p_i、n 构成。",
                "难点不是模拟删除，而是把各种删除过程转成区间极值和 RMQ 判定。",
            ],
            "solution_brief": "关键观察：删除中位数会保留区间两端意义上的极小/极大结构。先特判 p_i 为全局最小或最大；再用前缀/后缀极值判断能否到 4；最后围绕 pos(1)、pos(n)、i 的相对位置，用区间最小/最大查询判定是否能进一步到 3，否则答案为 5。",
            "primary_topic": "构造与贪心",
        },
        "2207H3": {
            "statement_brief": "交互还原一个按变量顺序构造的 min-max 表达式树，并在询问次数限制内回答后续函数值；困难版总变量数更大。",
            "transformed_statement": "把题目先看成：min/max 表达式可化为一棵叶子按顺序排列、内部 min/max 交替的树；交互目标是恢复这棵树。",
            "key_observations": [
                "相邻同类 min 或 max 节点可压缩，得到沿根到叶交替的树结构。",
                "询问 f(1,2,...,n) 得到的 z，是从根出发时在 max 节点走最右孩子、在 min 节点走最左孩子抵达的关键叶。",
                "若 z 在端点，可以把端点作为根的叶子剥掉，递归恢复剩余函数。",
                "若 z 在中间，构造左限制函数和右限制函数：右侧填正无穷、左侧填负无穷，分别递归恢复 z 两边的子结构。",
                "剩下只需判断从 x_z 往根的挂接顺序；题解用五段赋值询问区分下一步接左子树还是右子树，并用双指针合并。",
            ],
            "solution_brief": "关键观察：一次全递增询问能定位主路径叶 z，之后左右限制函数把问题拆开。递归恢复左右子树后，用常数模式的比较询问不断决定挂接顺序，最终得到完整 min-max 树；回答阶段直接在树上求值。",
            "primary_topic": "交互",
        },
        "2190F": {
            "statement_brief": "给 x 和 k，任选非负 y，考虑两个长度为 k 的连续整数区间两两异或所得集合 S(x,y,k)，求这个集合大小的最大值。",
            "transformed_statement": "把题目先看成：连续区间的异或笛卡尔积可以按最高不同位拆成少数区间，再对 y 做数位 DP 最大化。",
            "key_observations": [
                "两个区间共有的高位前缀会在异或中抵消，因此可先删去共同前缀再分析。",
                "基础块 S(0,0,k,l) 会形成从 0 到最大可达异或值的一段连续区间。",
                "一般区间跨过最高位边界时，可拆成左半和右半；四种异或笛卡尔积最终合并成两个互不相交的值域区间。",
                "固定 x 后，y 的有效形态只和若干高位拆分参数有关，不需要枚举 y。",
                "最终目标函数由两个 min 项组成，状态只需维护 x 区间和 y 区间在当前二进制位下的拆分信息。",
            ],
            "solution_brief": "关键观察：集合大小先被推成关于区间端点最高位拆分的公式，再优化 y。先去共同前缀，推导 S(x,y,k) 的两个区间长度表达式；随后用数位 DP 枚举 y 与 x 的最高位关系和左右剩余长度，取最大集合大小。",
            "primary_topic": "动态规划与状态设计",
        },
        "2183C": {
            "statement_brief": "n 个基地排成一线，首都在 k。每天可让一个基地内任意数量士兵统一左移或右移一步，随后首都新增一名士兵；m 天后最大化有士兵的基地数。",
            "transformed_statement": "把题目先看成：最终有兵的基地一定是一段包含 k 的连续区间，问题变为判断左右各扩多少格是否来得及。",
            "key_observations": [
                "士兵只能逐步移动，若最终占据某个远点，则中间路径上的基地也能被占据，所以最优形态是包含首都的连续区间。",
                "设向左扩 a 格、向右扩 b 格，总共至少需要 a+b 个新士兵到达这些新基地。",
                "更长的一侧需要形成流水线；除了产生士兵的天数外，还要额外等待 max(a,b)-1 天让最远士兵走到位。",
                "因此可行条件是 a+b+max(a,b)-1 <= m。",
                "有了这个判定后，扩短边通常更划算，贪心尝试增加左右扩展即可。",
            ],
            "solution_brief": "关键观察：不要模拟每个士兵，先把目标压成连续区间。维护左右已扩长度 a、b，每次尝试扩一格并用 a+b+max(a,b)-1 <= m 判可行；在边界范围内贪心扩展，得到最大区间长度。",
            "primary_topic": "构造与贪心",
        },
        "2156F1": {
            "statement_brief": "给一个排列。一次操作可选 i<j<k，若三个值是连续整数且 p_i 最大，则把 p_i 减 2，另两个各加 1。求可达的字典序最小排列；简单版数据较小。",
            "transformed_statement": "把题目先看成：从左到右固定字典序最小前缀，每次只关心当前首元素能否变成 1 或 2。",
            "key_observations": [
                "当前首元素若为奇数，可以通过连续值三元操作一路降到 1。",
                "当前首元素若为偶数，正常最低只能降到 2；想让 1 提前出现，需要先找到一个可被移动到前缀效果中的奇数。",
                "能用来制造 1 的奇数必须足够靠左，并且它左边尚未固定的值都比它大，否则字典序会先被更小位置阻塞。",
                "固定 1 或 1、2 之后，剩余值整体平移，仍是同一种问题。",
                "简单版可以直接递归/模拟，不需要复杂数据结构维护这些条件。",
            ],
            "solution_brief": "关键观察：字典序目标让问题自然按前缀递归。若首元素为奇数，把它降到 1 后删除固定；若为偶数，检查是否存在满足条件的奇数先生成 1，再把首元素降到 2。每固定一段前缀后，对剩余排列重标号继续处理。",
            "primary_topic": "构造与贪心",
        },
        "2156D": {
            "statement_brief": "交互题。隐藏 1..n 的排列，但不能询问最后位置；每次可询问 p_i 与 x 的按位与是否非零，要求用至多 2n 次询问确定 p_n。",
            "transformed_statement": "把题目先看成：逐位确定 p_n，同时每确定一位就把候选位置和值按低位前缀过滤掉。",
            "key_observations": [
                "若知道前 n-1 个位置第 k 位为 1 的数量，就能用全集 1..n 的第 k 位计数反推出 p_n 的第 k 位。",
                "朴素逐位询问所有位置是 n log n，超过限制。",
                "确定低位后，只保留那些低位前缀与 p_n 相同的位置和数值；下一位只需要询问这些候选位置。",
                "候选集合每轮大约减半，所以总询问数是 n+n/2+n/4+...，小于 2n。",
                "关键是同步维护“可能是 p_n 同前缀的值集合”和“对应位置集合”，而不是独立恢复每个 p_i。",
            ],
            "solution_brief": "关键观察：位计数差分可以恢复 p_n，但必须边恢复边筛候选。按位从低到高处理，对当前候选位置询问该位；与候选值集合的该位计数比较得到 p_n 该位，然后过滤出低位前缀相同的候选，直到确定完整答案。",
            "primary_topic": "交互",
        },
        "2128C": {
            "statement_brief": "初始数组全 0。每次选择 x 大于当前最小值，系统找到最左的 a_i<x 并给它加 x。问能否到达目标数组 b。",
            "transformed_statement": "把题目先看成：对每个位置 i，最后一次给它加的 x 必须不超过左侧目标前缀最小值，由此得到局部充要条件。",
            "key_observations": [
                "令 m_i 为 b_1..b_{i-1} 的最小值；位置 i 的操作会被左侧所有值是否至少为 x 所约束。",
                "看最后一次增加 a_i 的操作：操作前 a_i<x，操作后达到 b_i，因此 b_i<=2x-1。",
                "同时 x 不能超过左侧最终前缀最小值 m_i，所以必要条件是 b_i<=2m_i-1。",
                "这个条件也是充分的：若 b_i<m_i，直接加 b_i；否则分两次加 b_i-m_i 和 m_i。",
                "因此全题不需要搜索操作序列，只需扫一遍前缀最小值。",
            ],
            "solution_brief": "关键观察：最后一次操作给出一条强约束，并且这条约束刚好可构造。维护左侧最小值 m；对每个 i>=2 检查 b_i<=2m-1，然后更新 m=min(m,b_i)。全部满足输出 YES，否则 NO。",
            "primary_topic": "构造与贪心",
        },
        "2127F": {
            "statement_brief": "数组元素在 0..m，和为 m，且最后一个元素是全局最大值。按给定伪代码定义 f(a)，求所有这类数组的 f(a) 总和。",
            "transformed_statement": "把题目先看成：先把伪代码化简成若干位置贡献，再固定最大值 x 做带上界的整数拆分计数。",
            "key_observations": [
                "伪代码访问序列可按遇到新最大值分段，f(a) 等于访问到的最大值之和，减去每个最大值后第一个元素之和，再减 a_1。",
                "固定最大值 x 后，其余位置只需满足 0<=a_i<=x 且总和固定。",
                "带上界的非负整数解个数 g(n,m,x) 可用容斥加插板公式计算。",
                "a_1 的总贡献不用逐位枚举：在固定 a_n=x 后，前 n-1 个位置对称，总和均摊即可。",
                "最大值后的第一个元素贡献需要按“某位置为 x 且后继是多少”拆开统计，但仍能复用同一个 g。",
            ],
            "solution_brief": "关键观察：先读懂 f(a) 才能计数。把 f 化成“最大值贡献 - 最大值后继贡献 - a_1”；枚举最大值 x，用容斥插板计算 g(n,m,x)，分别累加最大值出现、a_1 对称平均和后继元素三类贡献，整体按 m 的调和复杂度优化。",
            "primary_topic": "组合计数与概率",
        },
        "2113F": {
            "statement_brief": "给两个长度为 n 的数组，每个位置可选择是否交换上下元素。最大化两个数组中不同值数量之和，并输出一种达到最大值的构造。",
            "transformed_statement": "把题目先看成：每个位置是一条连接 a_i 和 b_i 的无向边，选择是否交换就是给边定向；希望出现至少两次的值在上下两行都出现。",
            "key_observations": [
                "某个值 x 的贡献上限是 min(cnt_x,2)，因为它最多能在两行各贡献一次。",
                "若把边定向为上端到下端，则一个值是否出现在两行，等价于对应点是否既有入边又有出边。",
                "所以目标变成：让每个度数至少 2 的点都有至少一条入边和至少一条出边。",
                "对每个连通块建 DFS 树，树边向下、返祖边向上，除根外的点天然同时拥有入出方向。",
                "若根度数至少 2 但缺少某个方向，翻转根的一个子树即可补齐，不会破坏其他点的条件。",
            ],
            "solution_brief": "关键观察：数组交换问题可变成图定向问题。先按值建图，每个下标是一条边；在每个连通块中 DFS 定向，必要时翻转一个子树修正根。最后按边方向决定是否交换对应位置，即可达到 sum min(cnt_x,2) 的上界。",
            "primary_topic": "图论与网络流",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2107F2": {
            "statement_brief": "困难版 Cycling：对每个前缀，Leo 从最后一个骑车人后面出发，可花费当前前方骑车人的敏捷值超车，也可花费距离交换两个敏捷值，求超到最前的最小代价。",
            "transformed_statement": "把题目先看成：每个后缀先用当前最小敏捷值处理一段超车，困难版要把这个后缀 DP 在线维护到所有前缀答案。",
            "key_observations": [
                "简单版中，当前后缀的第一个最小值 p 一定值得先拿来用，因为它比 p 前面的值便宜，且换到前面不会更差。",
                "原本可能枚举把 p 带到任意 q；困难版的关键性质是最优 q 只会是 p 或后缀末尾 n。",
                "因此沿着连续后缀最小值位置 p_1,p_2,...，最优策略等价于选择某个 p_x 把它一路带到末尾，之前的最小值都不带走。",
                "固定这个选择后，对前缀长度的贡献是一条线性函数。",
                "每次在末尾追加元素最多只新增一个候选线性函数，所以可用凸包或 Li Chao 树维护最小值。",
            ],
            "solution_brief": "关键观察：把 F1 的 O(n^2) 枚举 q 收紧成只看边界 q=p 或 q=n。维护所有“选择第 x 个后缀最小值带到末尾”的线性代价函数；按前缀从短到长加入新候选，并查询当前长度的最小值，即得到每个前缀答案。题解还给了只考虑 min(a)..min(a)+20 的简化方向。",
            "primary_topic": "动态规划与状态设计",
        },
        "2102A": {
            "statement_brief": "给 n、m、p、q，问是否存在一个长度 n 的整数数组，总和为 m，且任意连续 p 个元素的和都等于 q；元素可以为负。",
            "transformed_statement": "把题目先看成：连续 p 段和相等会强迫数组以 p 为周期，唯一需要检查的是完整周期块的总和。",
            "key_observations": [
                "相邻两个长度 p 的窗口和相等，二者相减得到 a_i=a_{i+p}。",
                "所以只要前 p 个数确定，后面所有位置都被周期性唯一确定。",
                "若 n 能被 p 整除，数组由 n/p 个完整周期块组成，总和必须等于 q*(n/p)。",
                "若 n 不能被 p 整除，末尾不完整块给了额外自由度；因为允许负数，可以任意调节总和差额。",
            ],
            "solution_brief": "关键观察：窗口条件等价于 p 周期。若 n%p==0，只需判断 m 是否等于 q*(n/p)；否则总能通过前 p 个数和不完整尾块的自由变量构造出所需总和，直接输出 YES。",
            "primary_topic": "构造与贪心",
        },
        "2062G": {
            "statement_brief": "给两个排列 p、q。一次可交换 p_i 和 p_j，代价为 min(|i-j|, |p_i-p_j|)，要求用最小总代价把 p 变成 q，并输出操作序列。",
            "transformed_statement": "把题目先看成：每个元素是平面点 (位置, 值)，交换代价允许沿横向或纵向搬动两个点；先求点到目标点的最小匹配，再把匹配拆成实际同步交换。",
            "key_observations": [
                "代价 min(|i-j|,|p_i-p_j|) 可拆成两种交换模式：按位置距离付费，或按值距离付费。",
                "把 p_i 看作点 (i,p_i)，目标 q_j 看作点 (j,q_j)，放松“两个点必须同时移动”后，移动成本就是曼哈顿距离的一半。",
                "因此最小可能代价先变成 p 点到 q 点的最小权完美匹配。",
                "题解证明这个放松不会降低不可达成本：横向移动时总能找到交叉的两条匹配边，通过交换同时推进两个点且不增加代价；纵向同理。",
                "所以先做最小费用匹配，再按匹配中的横纵移动逐步找可交换对，即可构造最优操作序列。",
            ],
            "solution_brief": "关键观察：把排列交换变成二维点匹配。用最小费用最大流或匈牙利求出每个当前点要去的目标点；随后先完成横坐标调整、再完成纵坐标调整，每次找一对区间交叉的点交换，保证总代价正好等于匹配下界。",
            "primary_topic": "图论与网络流",
        },
        "2061D": {
            "statement_brief": "给多重集合 a、b。一次可把两个差不超过 1 的数合并成它们的和，问能否把 a 变成 b。",
            "transformed_statement": "把题目先看成：正向合并难判断，反向从 b 不断把一个数 x 拆成 floor(x/2) 和 ceil(x/2)，看能否精确拆回 a。",
            "key_observations": [
                "操作保持总和不变，所以总和不同必然无解。",
                "若一个数 x 是由两个差不超过 1 的数合并而来，那么反向拆分方式唯一：floor(x/2) 和 ceil(x/2)。",
                "始终处理当前 b 中最大的数：若它能和 a 中最大的同值抵消，就直接匹配；否则它必须继续拆小。",
                "如果当前最大 b 已经小于当前最大 a，就再也不可能拆出这个 a 值。",
                "总共只需拆 n-m 次，之后所有数必须一一匹配。",
            ],
            "solution_brief": "关键观察：反向唯一拆分把搜索变成贪心。先检查总和；用两个 multiset 或优先队列维护 a 与当前 b，每次比较最大值，相等就删除两边，否则把 b 的最大值拆成两半。过程中若 b 最大值小于 a 最大值或拆分次数超限，则输出 NO。",
            "primary_topic": "构造与贪心",
        },
        "2034G2": {
            "statement_brief": "给若干闭区间，要给每个区间染色，使任意被覆盖的整数时刻都存在一种颜色恰好出现一次；求最少颜色并构造。困难版只在整数点检查。",
            "transformed_statement": "把题目先看成：先判 1 色、再判 2 色；若 2 色不行，题解给出一个 3 色贪心构造保证可行。",
            "key_observations": [
                "1 色可行当且仅当没有任意整数点被两个以上区间覆盖。",
                "3 色总能构造：从左到右取覆盖当前未处理点且右端最远的区间，交替使用 1、2 形成唯一覆盖链，其余冲突交给第 3 色。",
                "判 2 色的关键是“唯一颜色区间”的延续性：若某区间能在时刻 x 成为唯一颜色，它可以一直维持到自己的右端。",
                "因此颜色状态只会在线段端点附近发生 O(n) 次变化，不需要逐点扫描巨大坐标。",
                "困难版只看整数点，所以要压缩 l_i-1、l_i、r_i、r_i+1 这些事件边界。",
            ],
            "solution_brief": "关键观察：答案只可能是 1、2、3。先扫压缩坐标判是否无重叠；再用事件集合维护当前哪些区间能作为唯一颜色，若全过程可维持则构造 2 色；否则使用右端最远覆盖链的 3 色贪心构造。",
            "primary_topic": "构造与贪心",
        },
        "2030F": {
            "statement_brief": "定义一个数组可被不断删除同值连续块且每个值只能选一次时为 orangutan-approved。给数组 a 和多次区间询问，判断子数组是否满足这个性质。",
            "transformed_statement": "把题目先看成：坏区间的本质是两个值交叉出现，形成 x,y,x,y 的子序列模式。",
            "key_observations": [
                "题解给出充要条件：数组不可删除当且仅当存在 w<x<y<z，使 b_w=b_y、b_x=b_z 且这两个值不同。",
                "如果没有这种交叉模式，按第一个值的所有出现位置切开，中间各段的值集合互不相交，可以递归删除。",
                "所以对固定右端 r，只需找到最靠左的 left[r]，使 [left[r],r] 仍没有交叉模式。",
                "扫描右端时，新加入 a_i 只会和它的上一次出现 last[i] 相关；若 last[i] 左侧到当前左边界之间存在一个值的下一次出现越过 last[i]，就形成交叉。",
                "用 next 位置的最大值线段树和双指针维护 left[r] 后，每个询问只需判断 l>=left[r]。",
            ],
            "solution_brief": "关键观察：可删除性等价于不存在 x,y,x,y 的交叉子序列。预处理每个位置的上一次/下一次同值位置，右端从左到右推进，用线段树检查是否出现跨过 last[i] 的 next；必要时移动左端。得到 left[r] 后，查询 [l,r] 的答案就是 left[r]<=l。",
            "primary_topic": "数据结构",
        },
        "2029I": {
            "statement_brief": "给数组 a。一次操作可选择一个区间整体加 k；对每个 p=1..m，求恰好做 p 次操作后方差的最小值，并输出乘以 n^2 的结果。",
            "transformed_statement": "把题目先看成：枚举最终平均值对应的参数 x；固定 x 后，问题变成每次选一个区间，使平方误差增量尽可能小。",
            "key_observations": [
                "方差等于 min_x sum(b_i-x)^2，因此可以先枚举可能的平均值参数，再最小化这个平方和。",
                "做 p 次区间加 k 后，总和只会按 k 的整数倍变化，所以可能的 x 数量是 O(nm)。",
                "固定 x 后，某个位置已经被加了 c 次时，再加一次的边际代价是一个随 c 递增的凸函数。",
                "区间操作可建成路径上的最小费用流；由于边际代价凸，实际可以用“每次选当前最优区间”的后悔贪心实现。",
                "代码里同时考虑继续给某段加一次和撤回/调整某段历史选择，等价于最小费用流的增广过程。",
            ],
            "solution_brief": "关键观察：先把方差目标改写成固定中心 x 的平方误差最小化。枚举所有可能的 x；对每个 x，维护每个位置下一次加 k 的边际增量，反复找最小区间增量并更新，得到 1..m 次操作的候选答案；所有 x 取最小。",
            "primary_topic": "图论与网络流",
        },
        "2027E2": {
            "statement_brief": "有 n 堆取石游戏，每堆可取 d，要求 d 是当前石子数 x 的子掩码且 d<=a_i。困难版给定 a_i、b_i，要统计所有 1<=x_i<=b_i 中 Bob 必胜的游戏数。",
            "transformed_statement": "把题目先看成：先求单堆 Sprague-Grundy 值分布，再做异或为 0 的背包计数。",
            "key_observations": [
                "多堆公平组合游戏只看每堆 SG 值的异或；Bob 必胜等价于所有堆 nimber 异或为 0。",
                "简单版先把单堆 f(x,a) 通过二进制关系化成某个 a'，再落到 x=2^k-1 的标准形。",
                "单堆 nimber 只会落在少数四类：2^k-2、2^k-1、2^k、以及中间区间，对应值均不超过约 31。",
                "困难版真正要数的是：对每个 i 和每个 nimber p，有多少 x<=b_i 会让 f(x,a_i)=p。",
                "这个计数用数位 DP 完成，状态记录最高位位置、a' 的形态、是否已经小于 b，以及是否出现过 good bit。",
            ],
            "solution_brief": "关键观察：先把所有 x 的选择压成 32 个 nimber 计数。对每堆用数位 DP 统计 cnt[p]；然后做小范围异或背包，转移 dp[new_xor]+=dp[old_xor]*cnt[p]。最后 dp[0] 就是 Bob 必胜方案数。",
            "primary_topic": "博弈",
        },
        "2020A": {
            "statement_brief": "给 n、k。一次可从 n 中减去任意 k 的非负整数次幂，求把 n 减到 0 的最少操作数。",
            "transformed_statement": "把题目先看成：用 k 进制表示 n，每次减一个 k^x 就是在某一位减 1。",
            "key_observations": [
                "当 k=1 时，每次只能减 1，答案就是 n。",
                "对 k>1，除了减 1 的操作外，其他 k^x 都不改变 n mod k。",
                "因此至少需要 n mod k 次减 1，才能把当前 n 变成 k 的倍数。",
                "一旦 n 能被 k 整除，处理 n 等价于处理 n/k；多做 k 次减 1 不如一次减 k。",
                "递归下去，答案就是 n 在 k 进制下各位数字之和。",
            ],
            "solution_brief": "关键观察：最优策略等价于按 k 进制逐位清空。若 k=1 输出 n；否则循环累加 n%k，并令 n//=k，直到 n 为 0。",
            "primary_topic": "数论与同余",
        },
        "2247A": {
            "statement_brief": "数组只含 -1 和 1。一次可同时翻转相邻两个数的符号，问能否让数组总和变成 0。",
            "transformed_statement": "把题目先看成：一次操作会让总和改变 -4、0 或 4，所以只需判断总和模 4，并证明模 4 为 0 时一定可构造。",
            "key_observations": [
                "翻转相邻两个数时，它们对总和的贡献变化只能是 -4、0 或 4。",
                "因此总和 mod 4 是不变量；若初始总和不被 4 整除，必然无解。",
                "若总和被 4 整除，可以从左到右依次操作，把前 n-1 个位置调成 1,-1,1,-1 的交替形态。",
                "此时总和绝对值不超过 2，而它仍然被 4 整除，所以只能是 0。",
            ],
            "solution_brief": "关键观察：必要条件 sum%4==0 也是充分条件。实现时不用真的输出操作，只需计算数组和，判断 abs(sum)%4 是否为 0。",
            "primary_topic": "数论与同余",
        },
        "2234E": {
            "statement_brief": "某个排列 p 中，a_i 表示有多少区间的最小值恰好是 p_i。给数组 a，求有多少个排列 p 能产生它。",
            "transformed_statement": "把题目先看成：最小值会把区间递归分成左右两半，a_i 必须等于它作为当前区间最小值时覆盖的区间数量。",
            "key_observations": [
                "在当前递归区间 [l,r] 内，若 p_i 是该区间最小值，则以 i 为最小值的区间数正好是 (i-l+1)*(r-i+1)。",
                "所以必须在 [l,r] 中找到某个满足 a_i=(i-l+1)*(r-i+1) 的位置作为当前最小值；找不到则无解。",
                "选定 i 后，当前最小值本身唯一，剩余较大的数可以任意分配给左、右子区间。",
                "因此贡献为 左答案 * 右答案 * C(r-l, i-l)。",
                "从区间两端交替向内找合法 i，可以把总复杂度从 O(n^2) 摊到 O(n log n)。",
            ],
            "solution_brief": "关键观察：数组 a 反推出的是笛卡尔树式递归结构。递归处理 [l,r]，找满足乘积公式的位置 i；若存在，乘上组合数 C(r-l,i-l) 并递归左右。为了避免最坏 O(n^2)，每段按 l,r,l+1,r-1 的顺序找候选位置。",
            "primary_topic": "组合计数与概率",
        },
        "2229A": {
            "statement_brief": "若干 slime 在数轴上。一次选择 x，所有小于 x 的位置加 1，所有大于 x 的位置减 1，等于 x 的不变；求让所有 slime 重合的最少操作数。",
            "transformed_statement": "把题目先看成：最终位置 y 固定后，每次都选 x=y 最优，答案只取决于最左和最右 slime 到 y 的最大距离。",
            "key_observations": [
                "若最终都到 y，选择 x=y 会让所有未到 y 的 slime 同时朝 y 走一步，不会浪费。",
                "因此固定 y 时所需操作数是 max(y-min(a), max(a)-y)。",
                "要最小化这个最大距离，y 应尽量靠近最小值和最大值的中点。",
                "最终答案就是 ceil((max(a)-min(a))/2)。",
            ],
            "solution_brief": "关键观察：中间位置的 slime 不影响答案，只看当前区间直径。读入后取 mn、mx，输出 (mx-mn+1)//2。",
            "primary_topic": "基础实现与模拟",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2226C": {
            "statement_brief": "给一个非负整数数组 a。每个位置可独立选择正整数 b_i，并把 a_i 变成 a_i mod b_i；恰好操作一次后，求能得到的最大 mex。",
            "transformed_statement": "把题目先看成：判断能否把不同位置分别变成 0..k-1，每个目标值只能占用一个原数组元素。",
            "key_observations": [
                "固定原值 x，它能保持为 x；若要通过取模变成别的值 z，则必须有 z<x/2，且任意 z<x/2 都能做到。",
                "所以目标值 v 可由某个 a_i=v 直接提供，或由某个 a_i>2v 的更大数取模得到。",
                "若 k 可行，则 k-1 也可行，因此可以二分答案。",
                "检查 k 时从 k-1 递减到 0 分配元素：优先用等于 v 的元素，否则用一个大于 2v 的未用元素。",
                "从大目标往小目标处理，是因为大目标可用的大数范围更窄，小目标更容易被剩余大数补上。",
            ],
            "solution_brief": "关键观察：取模后的可达值只有“原值本身”或“小于原值一半”的值。二分 mex=k；用 multiset 检查 0..k-1 是否能各自匹配一个元素，按 v 从大到小，能用精确 v 就用，否则找 a_i>2v 的元素。最大可行 k 即答案。",
            "primary_topic": "构造与贪心",
        },
        "2210B": {
            "statement_brief": "有 n 把椅子和一个排列 p。按顺序访问椅子，若当前椅子已被标记则游戏结束；否则可坐下并标记 p_i，或跳过。求最多能坐多少把椅子。",
            "transformed_statement": "把题目先看成：假设游戏在第 k 把椅子结束，哪些 k 之前的椅子可以安全坐下。",
            "key_observations": [
                "若坐第 i 把椅子会标记 p_i；在游戏结束点 k 之前，只有标记到 [i+1,k-1] 才会提前挡路。",
                "因此在固定结束点 k 时，可坐的 i<k 满足 p_i<=i 或 p_i>=k。",
                "看似要枚举 k，但题解用交换论证说明，把结束点推到 n+1 不会更差。",
                "直觉是：那些为了较早结束点而允许的 p_i>=k，可以和右侧 p_j<=j 的安全椅子交换贡献。",
                "所以最优就是尽量不提前结束，只坐所有 p_i<=i 的椅子。",
            ],
            "solution_brief": "关键观察：真正安全的椅子是坐下后只标记自己或左侧的位置。直接统计满足 p_i<=i 的下标数量；这等价于选择 k=n+1 的最优结束点。",
            "primary_topic": "构造与贪心",
        },
        "2178C": {
            "statement_brief": "一排孩子，每次必须移除当前第一或第二个孩子。移除第一个给 X 加 a_i，移除第二个给 X 减 a_i，最后留一个孩子不计分；求 X 最大值。",
            "transformed_statement": "把题目先看成：枚举最终没被选的孩子，左侧中间段的符号可自由选择，右侧孩子被迫取负号。",
            "key_observations": [
                "原始第一个孩子只要不是最终留下的那个，就一定只能作为第一位被移除，贡献 +a_1。",
                "最终留下位置右侧的孩子永远被它挡在后面；这些孩子若被选，只能作为第二个孩子移除，贡献 -a_i。",
                "第一个孩子和留下位置之间的孩子，可以独立决定贡献是 +a_i 还是 -a_i。",
                "这种独立性可构造：若想让当前第二个孩子取负就直接选第二个，否则选第一个推进队列。",
                "所以固定留下位置后，最优贡献由 +a_1、前缀绝对值和、后缀负和三部分组成。",
            ],
            "solution_brief": "关键观察：枚举唯一没选的孩子即可。预处理 i>=2 的 |a_i| 前缀和与 -a_i 后缀和；若留下 u，答案候选为 u!=1 时的 a_1，加上 2..u-1 的绝对值贡献，再加上 u+1..n 的负贡献，取最大。",
            "primary_topic": "构造与贪心",
        },
        "2164E": {
            "statement_brief": "在带权无向连通图上从 1 出发，要拍照标记每条边至少一次并回到 1。可以沿边拍照付边权，也可以坐火车跳到任意点，火车费用是所选路径上最大编号边对应的权值。求最小费用。",
            "transformed_statement": "把题目先看成：先付出每条边拍照一次的基础费用；若奇度点无法形成欧拉回路，就用火车虚边把奇度点两两配对。",
            "key_observations": [
                "每条边至少要拍一次，因此基础费用至少是所有边权之和；若所有点度数为偶数，沿欧拉回路刚好达到这个下界。",
                "非欧拉图中，需要补一些不拍照的虚边，使奇度点成对配平；最优只需给每对奇度点加一条火车虚边。",
                "火车费用不是普通最短路，而由路径最大边编号对应的权值决定。",
                "按边编号建 Kruskal 重构树后，两点路径所需的最小“最大编号”由它们在重构树上的 LCA 及其祖先刻画。",
                "对每个重构树内部点预处理从它到祖先链上的最小边权 f，DFS 时在同一子树内尽早配对剩余奇度叶子，费用为 f_x。",
            ],
            "solution_brief": "关键观察：这是欧拉补边问题，但补边费用要用重构树计算。答案先加 sum(w)；按编号建重构树并预处理祖先链最小权 f；在树上 DFS，子树内每出现两个未匹配奇度原点就用当前 f_x 配掉，最后累加这些虚边费用。",
            "primary_topic": "图论与网络流",
        },
        "2157H": {
            "statement_brief": "要求输出最多 2000 个长度 n 的 bitonic 排列，使其作为置换时恰好有 m 个循环。",
            "transformed_statement": "把题目先看成：先处理等价的 anti-bitonic 排列，再用小规模枚举和两个扩展操作覆盖大 n。",
            "key_observations": [
                "bitonic 与 anti-bitonic 可通过反转并取补建立双射，所以构造 anti-bitonic 更方便。",
                "已有 (n,m) 的解时，末尾追加 n+1 可得到 (n+1,m+1) 的解。",
                "已有 (n,m) 的解时，末尾追加 n+1 后再调整 p_1，也可得到 (n+1,m) 的解。",
                "n<=18 时可以枚举所有 anti-bitonic 排列并数循环，作为基础解库。",
                "当 n-m 很小时，循环很多意味着固定点很多；anti-bitonic 结构会迫使 p_1<=19，因此只需枚举很小的前缀。",
            ],
            "solution_brief": "关键观察：不要直接搜索 n<=100。分三类处理：小 n 直接枚举；n 大且 n-m>=10 时，从 n=18 的足量样例用两个扩展操作推到目标；n 大且 n-m<=9 时利用固定点数量推出 p_1 很小，只枚举前 19 附近的 anti-bitonic 结构，最后映射回 bitonic 输出。",
            "primary_topic": "构造与贪心",
        },
        "2140B": {
            "statement_brief": "给正整数 x，构造正整数 y<1e9，使十进制拼接数 x#y 能被 x+y 整除。",
            "transformed_statement": "把题目先看成：设 y 有 d 位，把拼接写成 x*10^d+y，再主动让 x+y 成为容易整除的因子。",
            "key_observations": [
                "若 y 有 d 位，则 x#y=x*10^d+y=x*(10^d-1)+(x+y)。",
                "因此只要 x+y 能整除 x*(10^d-1)，就能整除 x#y。",
                "对任意 d>0，10^d-1 都能被 3 整除。",
                "令 x+y=3x，即 y=2x，就保证 x+y 整除 x*(10^d-1)。",
                "由于 x<1e8，2x 一定小于 1e9，满足输出范围。",
            ],
            "solution_brief": "关键观察：拼接数减去 x+y 后变成 x*(10^d-1)。直接输出 y=2x，此时 x+y=3x，而 10^d-1 总被 3 整除，所以条件成立。",
            "primary_topic": "数论与同余",
        },
        "2134A": {
            "statement_brief": "长度 n 的白格中，先涂一段长度 a 的红色，再涂一段长度 b 的蓝色覆盖红色。问是否能让最终颜色关于中心对称。",
            "transformed_statement": "把题目先看成：最终一定可见的蓝色连续段必须居中；若红段没有被蓝段完全覆盖，红色可见部分也必须整体居中。",
            "key_observations": [
                "蓝色段最后涂，所有 b 个蓝格都会出现在最终图案中，所以它必须能放在网格正中。",
                "长度 b 的连续段能居中，当且仅当 n 和 b 奇偶性相同。",
                "若 a<=b，红色可以完全被蓝色覆盖，红段位置不再影响最终颜色。",
                "若 a>b，会有红色露出；为了最终对称，长度 a 的红段也必须能居中。",
                "因此 a>b 时还要 n 和 a 奇偶性相同。",
            ],
            "solution_brief": "关键观察：只检查能否居中。若 a<=b，判断 n%2==b%2；否则判断 n、a、b 三者奇偶性是否相同。",
            "primary_topic": "基础实现与模拟",
        },
        "2118F": {
            "statement_brief": "给两个循环意义下的数组 a、b，值域为 1..m 且每个值都出现。可左循环移位，也可交换相邻且差至少 2 的元素，问能否把 a 变成 b。",
            "transformed_statement": "把题目先看成：差至少 2 的元素相对顺序可被交换掉，真正不变量只来自相邻值 v 和 v+1 的嵌套相对位置。",
            "key_observations": [
                "只有数值差不超过 1 的两个元素相对顺序会受到限制；差至少 2 的相邻元素可以直接交换。",
                "把数组视为环，循环移位只会改变根序列的起点。",
                "对每个值 v 的一次出现，记录它到下一次 v 之间按顺序出现的 v-1，作为有序儿子。",
                "这样从值 m 的出现位置作为根，可以构造一组有序根树，完整表达所有相邻值层级关系。",
                "两个数组可互达，当且仅当这些根树哈希序列互为循环位移。",
            ],
            "solution_brief": "关键观察：可交换性把数组压成“相邻值嵌套森林”。分别为 a、b 构造从 m 到 1 的有序树森林，对每棵树做确定性哈希；最后用 KMP 或字符串哈希判断两组根哈希序列是否为循环旋转。",
            "primary_topic": "字符串",
        },
        "2081D": {
            "statement_brief": "完全图中每个点有权值 p_i，边权为 max(p_x,p_y) mod min(p_x,p_y)。求最小生成树总权。",
            "transformed_statement": "把题目先看成：不用枚举完全图，只为每个权值 x 连接每个倍数区间里最小的可用权值。",
            "key_observations": [
                "相同权值的点之间边权为 0，可以先视为同一类或加 0 边。",
                "对固定小权值 x，在区间 [k x,(k+1)x) 内，边权就是 y-kx。",
                "该区间里只有最小的 y 可能有用；更大的 z 可以通过这个 y 连接，代价不会更优。",
                "因此每个 x 只需枚举它的倍数边界 kx，并找不小于 kx 的最小存在权值。",
                "候选边数是调和级数级别 O(V log V)，再在候选边上跑 Kruskal 即可。",
            ],
            "solution_brief": "关键观察：MST 不需要完整图。排序/标记出现的权值，预处理每个位置右侧最近出现值；对每个 x 枚举 kx，连向该倍数区间的最小 y，边权为 y mod x。加入重复权值 0 边后，对所有候选边排序做 Kruskal。",
            "primary_topic": "图论与网络流",
        },
        "2063B": {
            "statement_brief": "给数组和区间 [l,r]。必须选择一个子序列并反转一次，求操作后 [l,r] 的最小可能区间和。",
            "transformed_statement": "把题目先看成：一次有效反转只需要从左侧前缀或右侧后缀向 [l,r] 换入小数，不需要同时使用两边外部元素。",
            "key_observations": [
                "如果选择的子序列同时包含 i<l 和 j>r，那么反转后这两个外部端点互换，不影响 [l,r] 内的值。",
                "删掉这样的外部端点对不会变差，因此最优子序列可限制在 [1,r] 或 [l,n] 其中一侧。",
                "固定在 [1,r] 内操作时，可以把这个范围里最小的 r-l+1 个值搬进目标区间。",
                "[l,n] 的情况完全对称。",
                "所以答案是两种候选范围内“取区间长度个最小值之和”的较小者。",
            ],
            "solution_brief": "关键观察：不能同时从目标区间左右两边获益。令 len=r-l+1；分别取 a[1..r] 中最小 len 个数之和、a[l..n] 中最小 len 个数之和，输出二者最小值。排序即可实现。",
            "primary_topic": "构造与贪心",
        },
        "2059D": {
            "statement_brief": "两张同点数无向连通图中各有一个 token。每步两个 token 同时沿各自图走到邻点，代价为两个新位置编号差的绝对值；无限步总代价要最小，否则输出无穷不可达。",
            "transformed_statement": "把题目先看成：要让无限总代价有限，最终必须进入两个 token 位于同编号点且之后能沿两图公共边来回走的零代价循环。",
            "key_observations": [
                "无限步总代价有限意味着从某一步开始每步代价都必须为 0，所以两个 token 之后总在同编号顶点上同步移动。",
                "若某个顶点 v 在两图中都有同一个邻点 u，则状态 (v,v) 可以沿公共边 v-u 来回走，后续代价全为 0。",
                "把这样的 v 标记为 good；问题变成从初始状态 (s1,s2) 到任意 (v,v) 且 v good 的最短路。",
                "状态图顶点是 (v1,v2)，一次转移枚举 v1 在图一的邻点 u1 和 v2 在图二的邻点 u2，边权为 |u1-u2|。",
                "若所有 good 对角状态都不可达，则答案为 -1。",
            ],
            "solution_brief": "关键观察：先找能无限零代价循环的 good 顶点，再在乘积图上求到它们的最短代价。建 n^2 个状态，从 (s1,s2) 跑 Dijkstra；答案取所有 good 顶点的 dist[(v,v)] 最小值，不存在则 -1。",
            "primary_topic": "图论与网络流",
        },
        "2035C": {
            "statement_brief": "构造 1..n 的排列，使从 k=0 开始依次执行奇数位按位 AND、偶数位按位 OR 后的最终 k 最大，并输出最大值和排列。",
            "transformed_statement": "把题目先看成：前面大部分数随便放，最后 3 到 5 个数负责把所有需要的二进制位调出来。",
            "key_observations": [
                "若 n 为奇数，最后一步是 AND，最终值不可能超过最后一个数，也就不可能超过 n；题解构造能达到 n。",
                "奇数 n 时，取 n 的最低位 l，把最后四个数安排为 l、另一个补位数、n-l、n，可在最后 AND 前把 k 调到 n。",
                "若 n 为偶数，最后一步是 OR，理论上可达到 1..n 所有数的按位 OR。",
                "偶数且 n 不是 2 的幂时，用最后三个数 n、n-1、最高位以下全 1 的数，就能补齐所有位。",
                "偶数且 n 是 2 的幂时需要最后五个数 1、3、n-2、n-1、n，先造低位全 1，再由 n 打开最高位。",
            ],
            "solution_brief": "关键观察：最大值只由最后少数位置控制。按 n 奇偶和是否为 2 的幂分类：奇数答案 n；偶数答案为 1..n 的按位 OR。把题解给出的特殊数放到排列末尾，其余未用数任意放前面即可。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2029E": {
            "statement_brief": "定义 x 能通过反复“加上当前 x 的某个不小于 2 的因子”变成 y 时，称 x 是 y 的生成元。给互不相同的数组 a，要求找一个公共生成元 x>=2，或判断不存在。",
            "transformed_statement": "把题目先看成：先判断数组里有没有质数；没有质数时 2 就能生成所有目标，有质数时公共生成元只能是那个质数本身。",
            "key_observations": [
                "2 可以生成所有合数，但不能生成奇质数；证明关键是对合数 x 减去它的最小因子后得到一个不小于 2 的偶数。",
                "质数不能由更小的数生成，因为最后一步必须从某个 x 加上它的因子到达该质数，这不可能。",
                "如果数组里有多个不同质数，公共生成元不存在；如果只有一个质数 p，只需检查 p 能否生成所有合数。",
                "偶数 x 可由 p 生成当且仅当 x>=2p。",
                "奇合数 x 的最大前驱是 x-最小因子(x)，因此 p 能生成 x 当且仅当 x-最小因子(x)>=2p。",
            ],
            "solution_brief": "关键观察：公共生成元的候选极少。用线性筛预处理质数和最小因子；若 a 中没有质数，答案为 2；若有两个以上不同质数，答案为 -1；否则设唯一质数为 p，逐个检查偶数 x>=2p、奇合数 x-最小因子(x)>=2p，全部通过则答案为 p。",
            "primary_topic": "数论与同余",
        },
        "2250B": {
            "statement_brief": "构造长度 n 的二进制串，使 0 和 1 的数量差不超过 1，且相邻相等的位置恰好有 k 个；若无法构造则输出 -1。",
            "transformed_statement": "把题目先看成：相邻相等对数由同字符极大连续块数量决定，若有 r 个极大连续块，则相邻相等对数正好是 n-r。",
            "key_observations": [
                "每个长度为 l 的连续块贡献 l-1 个相邻相等对，总贡献为 n-r。",
                "因此需要构造恰好 r=n-k 个连续块。",
                "因为 n>=2 且 0、1 数量差不超过 1，两个字符都必须出现，所以 r=1 时无解。",
                "r>=2 时，让块颜色交替；先给每块放一个字符，再把剩余的 0 塞进某个 0 块、剩余的 1 塞进某个 1 块。",
                "这样不会改变块数，只会改变块长，因此相邻相等对数仍是 k。",
            ],
            "solution_brief": "关键观察：不要直接构造相等边，先构造块数。令 r=n-k；若 r=1 输出 -1。否则按 0、1、0、1 交替生成 r 个块，每块先放一个字符，再把目标数量中剩余的同类字符追加到对应颜色的最后一个块中。",
            "primary_topic": "构造与贪心",
        },
        "2237B": {
            "statement_brief": "给初始数组 a 和严格递增目标值 b。第一阶段可把每个 a_i 增大任意非负量，第二阶段可相邻交换，要求最终得到 b，并最小化第二阶段交换次数。",
            "transformed_statement": "把题目先看成：每个 a_i 要匹配一个尚未使用且不小于 a_i 的目标 b_j；匹配后形成一个 b 的排列，交换次数就是把它排回递增顺序的逆序数。",
            "key_observations": [
                "对当前 a_i，若能匹配多个 b 值，选最小可行的 b_j 不会更差。",
                "交换论证：如果 a_i 选了更大的 b_j，而后面某个 a_m 选了较小的 b_i，由于 a_m<=a_i，可以互换目标值而不破坏可行性。",
                "所以从左到右贪心，每次取当前未用 b 中最小的 >=a_i。",
                "若某一步找不到这样的 b，则无法完成。",
                "贪心得到的是第二阶段开始时各位置的目标编号，最少相邻交换次数等于该编号序列的逆序数。",
            ],
            "solution_brief": "关键观察：先用“最小可行目标值”固定第一阶段，问题立刻变成逆序数。维护未使用的 b；依次给 a_i 匹配 lower_bound(a_i)，记录匹配到的 b 下标。若匹配失败输出 -1，否则 O(n^2) 统计下标序列逆序数即答案。",
            "primary_topic": "构造与贪心",
        },
        "2210C1": {
            "statement_brief": "简单版中 b_i=a_i。每个 a_i 最多改一次成不等于原值且不超过 b_i 的正整数，要求所有长度至少 2 的子数组 gcd 不变，最大化可操作位置数。",
            "transformed_statement": "把题目先看成：无需维护所有子数组 gcd，只要所有相邻二元 gcd 不变，任意更长子数组的 gcd 也会被保住。",
            "key_observations": [
                "长度 3 的 gcd 可写成 gcd(gcd(a_i,a_{i+1}), gcd(a_{i+1},a_{i+2}))，更长区间同理归纳。",
                "因此内部位置 i 只需同时保持 gcd(a_{i-1},a_i) 和 gcd(a_i,a_{i+1})。",
                "设这两个 gcd 分别为 A、B，新值必须同时是 A 和 B 的倍数，最小候选为 lcm(A,B)。",
                "简单版里 b_i=a_i 且新值不能等于原值，所以内部位置可操作当且仅当 lcm(A,B)<a_i。",
                "端点只有一个邻居，只需判断对应二元 gcd 是否小于端点原值。",
            ],
            "solution_brief": "关键观察：把全区间 gcd 条件压缩成相邻边条件。遍历位置：端点检查 gcd(端点,邻点)<端点；内部令 A=gcd(a_{i-1},a_i)、B=gcd(a_i,a_{i+1})，若 lcm(A,B)<a_i 则这个位置可降低。统计可降低位置数。",
            "primary_topic": "数论与同余",
        },
        "2187B": {
            "statement_brief": "给两个非负整数 x、y，找非负整数 p、q，使 p&q=0，并最小化 |x-p|+|y-q|。",
            "transformed_statement": "把题目先看成：冲突只来自 x、y 同时为 1 的最高位；必须让这一位在其中一个数中变成 0，再处理低位。",
            "key_observations": [
                "若 x&y=0，原数就是最优答案。",
                "否则取最高冲突位 b；任何可行解都必须在这一位破坏至少一边的 1。",
                "一种候选是把其中一个数向上加到该位进位清零，另一个数不动。",
                "另一种候选是保留高位，令一边在 b 位为 1 且低位清零，另一边在 b 位为 0 且低位全 1，从而低位互补。",
                "题解证明这个最高冲突位的局部处理已经足够达到全局最优；也存在 p=x 或 q=y 的最优解。",
            ],
            "solution_brief": "关键观察：不要逐位 DP，直接围绕最高共同 1 位造候选。分别尝试调整 x 或调整 y：向上进位清掉冲突位，或构造“高位不变、冲突位一边 1 一边 0、低位互补”的数对；过滤 p&q=0 后取距离和最小的候选。",
            "primary_topic": "构造与贪心",
        },
        "2180F2": {
            "statement_brief": "困难版小车控制：随机给每个网格交点一段朝四向之一的墙，车从左上角按“能下则下，否则能右则右，否则停止”的规则运动，统计满足条件的朝向方案数。",
            "transformed_statement": "把题目先看成：Easy 的四状态 DP 可按列分层；困难版的 m 很大，所以要把一整列的状态转移压成矩阵并快速幂。",
            "key_observations": [
                "简单版中每个格子的状态不仅取决于位置，还取决于车从上方还是左方进入，以及相关角点墙是否阻挡。",
                "固定列 j 后，所有 dp[i][j] 只依赖上一列和本列内部状态。",
                "每一列使用完全相同的转移规则，因此存在常量矩阵 M，使列状态满足 dp[j]=M*dp[j-1]。",
                "m 很大时不能逐列递推，直接计算 M^(m-1) 再乘初始向量。",
                "最终再把到达/出界概率换算为朝向方案数。",
            ],
            "solution_brief": "关键观察：困难版不是换 DP，而是把 Easy DP 的一列变成线性变换。枚举一列内的所有 i、进入方向、墙状态作为向量维度，构造列转移矩阵 M；用二进制快速幂求 M^m，乘初始状态后按题解公式还原答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2180F1": {
            "statement_brief": "简单版小车控制：随机给每个网格交点一段朝四向之一的墙，车从左上角按“能下则下，否则能右则右，否则停止”的规则运动，统计满足条件的朝向方案数。",
            "transformed_statement": "把题目先看成：车未来能否移动不只由所在格子决定，还取决于它是从哪边进入以及相邻角点墙的方向。",
            "key_observations": [
                "朴素 dp[i][j] 不够，因为同一个格子从上方进入和从左方进入，后续会检查不同的墙。",
                "题解把状态扩成四类：进入方向两种，加上当前会影响右移或下移的墙是否阻挡。",
                "例如从上方进入且右上角墙向下时，车无法右移，只能尝试下移；其他状态按墙方向概率分裂。",
                "四个状态都有固定的概率转移式，只依赖下方格子或右方格子的对应状态。",
                "按 i、j 逆序计算全部状态，最后用总朝向方案数减去到达出界的概率贡献。",
            ],
            "solution_brief": "关键观察：补足状态维度后才是普通网格 DP。定义 dp[i][j][进入方向][关键墙是否阻挡]，根据题解四个转移式逆序填表；起点按初始墙方向加权，得到失败/停留概率后乘 4 的交点数次方，转成朝向方案计数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2161G": {
            "statement_brief": "给数组 a 和 q 个独立查询 X。一次操作可让某个 a_i 加 1；对每个 X，求最少操作次数，使最终所有数的按位 AND 等于 X。",
            "transformed_statement": "把题目先看成：每个数至少要提升到最小的 y>=a_i 且 y&X=X；之后最多只需要额外改动一个数来消掉多余公共 1 位。",
            "key_observations": [
                "定义 up_X(z) 为最小 y>=z 且 y&X=X，任何最终 a'_i 都不能低于 up_X(a_i)。",
                "最优解中最多一个元素会超过自己的 up_X，因为多个元素额外打开的高位只需保留最高那个调整即可。",
                "基础代价是 sum(up_X(a_i)-a_i)；求 up_X 时，从 X 的高位到低位找 z 缺失的第一位并补齐低位。",
                "这些“包含若干高位但缺当前位”的元素数量和低位和，可用 OR 卷积预处理后快速回答。",
                "若 up 后所有数仍有某个多余公共 1 位，需要选一个缺该位的元素额外上调；但若只有一个数缺该位，它不能被选来破坏这个公共位。",
            ],
            "solution_brief": "关键观察：每个查询先算所有数到 up_X 的总提升，再处理 AND 中多出来的最高公共位。用 OR 卷积预处理按掩码包含关系的计数和低位和，快速求 sum(up_X-a_i)；再从高位枚举可额外上调的元素，取最小修正代价。",
            "primary_topic": "动态规划与状态设计",
        },
        "2158B": {
            "statement_brief": "长度 2n 的序列要分成两个长度 n 的子序列 p、q。f(seq) 表示出现次数为奇数的不同值数量，要求最大化 f(p)+f(q)。",
            "transformed_statement": "把题目先看成：每个值独立决定拆到 p、q 中的奇偶贡献，唯一全局约束是两边长度必须相等。",
            "key_observations": [
                "某个值总频次为 cnt，若拆成 u+v=cnt，它的贡献就是 u%2+v%2。",
                "cnt 为奇数时贡献必为 1；cnt≡2 mod 4 时可拆成两个奇数且不造成长度差，贡献为 2。",
                "cnt≡0 mod 4 时若想贡献 2，拆法会让两边长度差贡献为 ±2。",
                "设 x 是奇频值数、y 是 cnt≡2 mod 4 的值数、z 是 cnt≡0 mod 4 的值数，理论上限为 x+2y+2z。",
                "若 x>0 或 z 为偶数，可以平衡长度并达到上限；若 x=0 且 z 为奇数，模 4 长度差矛盾，必须少拿 2 分。",
            ],
            "solution_brief": "关键观察：只看每个值频次对 4 的余数。统计 x、y、z；若 x>0 或 z 为偶数，答案为 x+2y+2z；否则答案为 x+2y+2z-2。构造不需要输出，所以无需真的分配子序列。",
            "primary_topic": "组合计数与概率",
        },
        "2154B": {
            "statement_brief": "给数组 a，可免费把任意 a_i 变成前缀最大值，也可付费把任意 a_i 减 1。求最少付费次数，使数组满足 b1<b2>b3<b4...。",
            "transformed_statement": "把题目先看成：偶数位应尽量大、奇数位应尽量小；免费操作只会增大，所以应先把所有偶数位提升到对应前缀最大。",
            "key_observations": [
                "目标形态里偶数位是峰，奇数位是谷。",
                "操作 1 免费且只增大，最有价值的位置是偶数位；越早做不会让任何偶数位变差。",
                "对所有偶数位应用操作 1 后，偶数峰已经尽可能高，之后无法继续提高。",
                "剩下只需降低奇数位，让它严格小于相邻偶数峰。",
                "各个奇数位互不影响，位置 i 的代价是 max(0, a_i-min(相邻峰)+1)，边界只看唯一邻居。",
            ],
            "solution_brief": "关键观察：免费增大只服务峰位。先预处理前缀最大，并把偶数位视为对应前缀最大；随后遍历奇数位，计算降到小于左右峰所需的次数并求和。边界没有的邻居当作无限大或单独处理。",
            "primary_topic": "构造与贪心",
        },
        "2147G": {
            "statement_brief": "定义 b_0=1、b_n=a^{b_{n-1}}。若 b_n 最终恒等于 1 mod m，则称 a 对模 m 幂塔稳定。给 m=x*y*z，求这类正整数 a 的自然密度。",
            "transformed_statement": "把题目先看成：先固定 a mod m 和它在模 m 下的阶，把“高塔最终为 1”转成阶的所有质因子都必须整除 a。",
            "key_observations": [
                "当 gcd(a,m)=1 且 n 足够大时，b_n 形如 a^{a^N}，要等于 1 mod m 等价于 a^N 能被 ord_m(a) 整除。",
                "N 越来越大，所以条件等价于 rad(ord_m(a)) | a。",
                "因此可行性按模 m*phi(m) 周期化；固定 a mod m 后，能否选择 a+λm 满足 rad(ord_m(a)) 整除，由 CRT 判断。",
                "只有 gcd(ord_m(a),m)=1 的阶会贡献，密度可写成 (1/m)*sum cnt(x)/rad(x)，其中 x 枚举 phi(m) 的因子。",
                "再按 rad(x) 分组，用 Möbius 反演或容斥把求和化成乘积公式：1/m 乘以所有 (1+(q^β-1)/q)。",
            ],
            "solution_brief": "关键观察：指数塔稳定条件先落到乘法阶。分解 m 和 phi(m)，只保留 phi(m) 中不属于 m 的质因子 q^β；根据题解推导出的因子化公式，答案为 1/m 乘上所有 (1+(q^β-1)/q)。全程在模 998244353 下计算分数。",
            "primary_topic": "数论与同余",
        },
        "2135E1": {
            "statement_brief": "给长度 n 的二进制串计数问题。定义 f(r) 为反复同时删除所有 10 子串直到没有 10 后的结果；若 f(s)=f(反转(s))，则 s 是近回文串，要求计数。",
            "transformed_statement": "把题目先看成：删除 10 的过程会持续抵消可配对的 1 和 0，最终只剩若干 0 后接若干 1；但本地没有抓到该题题解正文。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留题意和一个直接来自题面过程的转换说明，避免根据旧总结、困难版题解或宽标签补写伪题解。",
            "primary_topic": "组合计数与概率",
            "extraction_status": "missing_editorial",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2120A": {
            "statement_brief": "给三个不能旋转、边平行的矩形，长和宽分别已按非增顺序给出，问能否无重叠拼成一个正方形。",
            "transformed_statement": "把题目先看成：三个矩形拼正方形时，形状只有两类：三块排成一条，或最大矩形占一整边、另外两块并排补齐剩余部分。",
            "key_observations": [
                "不能旋转且两维都已排序，所以不存在复杂的拼法枚举。",
                "三块排成一条时，要么三块长相等且宽之和等于边长，要么三块宽相等且长之和等于边长。",
                "分成上下或左右两层时，最大矩形必须单独占满正方形的一条边。",
                "剩下两块必须在另一方向尺寸相等，并且它们的并排长度刚好补满边长。",
            ],
            "solution_brief": "关键观察：只检查四个等式模式即可。分别判断三块横排、三块竖排、第一块在上另外两块在下、第一块在左另外两块在右；任一成立输出 YES，否则 NO。",
            "primary_topic": "几何",
        },
        "2096C": {
            "statement_brief": "给 n*n 高度矩阵。可各选若干行和列加 1，每行/列最多选一次且有费用；要求相邻上下或左右格高度都不同，求最小费用或无解。",
            "transformed_statement": "把题目先看成：行操作不会改变同一行内左右相邻格的差，列操作不会改变同一列内上下相邻格的差，所以横向约束和纵向约束可以独立求最小代价。",
            "key_observations": [
                "若左右相邻格相等，只能靠两列是否加 1 来打破；同一行整体加 1 对它们没有影响。",
                "若上下相邻格相等，只能靠两行是否加 1 来打破；同一列整体加 1 对它们没有影响。",
                "因此答案是“行选择满足纵向约束的最小费用”加上“列选择满足横向约束的最小费用”。",
                "每一行是否操作只有 0/1 两种状态，相邻两行是否合法可直接检查所有列。",
                "列问题可以转置矩阵后复用同一个二状态 DP。",
            ],
            "solution_brief": "关键观察：把二维互相干扰的操作拆成两个一维 DP。对行做 dp[i][0/1]，转移时枚举上一行是否加 1，检查每一列是否仍相等；列方向转置后同理。若任一方向最小值为无穷则无解，否则两者相加。",
            "primary_topic": "动态规划与状态设计",
        },
        "2084D": {
            "statement_brief": "给 n、m、k，且 m*k<n。需要构造长度 n 的非负整数序列，使删除至多 m 次长度 k 的连续段后，能得到的最小 mex 尽量大。",
            "transformed_statement": "把题目先看成：删除不会增加 mex，所以对手一定可以删满 m 次；目标是让 0 到答案减一的每个数在任意 m 次删除后都至少剩一次。",
            "key_observations": [
                "删满 m 次后剩余长度为 n-m*k，因此 mex 不可能超过 n-m*k。",
                "若要保证某个数不被完全删掉，它至少要出现 m+1 次，否则 m 次删除可以逐个消掉它的出现。",
                "所以 mex 也不可能超过 ⌊n/(m+1)⌋。",
                "上界是 min(n-m*k, ⌊n/(m+1)⌋)，题解给出两个周期构造正好达到它。",
                "当最终长度小于 k 时，按 i mod k 放值；否则按 i mod ⌊n/(m+1)⌋ 放值，使同值距离至少 k 且每个小值出现 m+1 次。",
            ],
            "solution_brief": "关键观察：先写出两个上界，再用周期序列同时卡住删除段。令目标值 res=min(n-m*k, ⌊n/(m+1)⌋)；若 res=n-m*k，则输出 i mod k 的模式；否则输出 i mod res 的模式。前者删除整段周期后仍保留前 res 个值，后者每次长度 k 删除最多删掉同一个值的一次出现。",
            "primary_topic": "构造与贪心",
        },
        "2071D1": {
            "statement_brief": "给无限 0/1 序列的前 n 项，后续 a_m 定义为前 ⌊m/2⌋ 项异或。简单版只有 l=r，要求查询单个位置的值。",
            "transformed_statement": "把题目先看成：先把序列补到 2n，再利用 a_{2m}=a_{2m+1} 的成对关系，把远处下标不断折半。",
            "key_observations": [
                "若 n 为偶数，先按定义补出第 n+1 项，把 n 变成奇数，之后配对消去才整齐。",
                "预处理前 2n 项后，小下标可以直接回答。",
                "当 2m>n 时，a_{2m}=a_{2m+1}=a_1 xor ... xor a_m。",
                "设 p 为前 n 项异或；因为 n 是奇数，n 之后的项可按相邻两项成对抵消。",
                "于是远处的 a_x 只需要异或一个 p，并视 x/2 的奇偶决定是否继续递归折半。",
            ],
            "solution_brief": "关键观察：远处下标不是展开前缀，而是不断除以 2。补齐到奇数 n 并预处理到 2n；查询 x>2n 时反复把答案异或前 n 项异或值 p，若当前折半位置对应的尾部成对完全抵消就停止，否则令 x=⌊x/2⌋ 继续。",
            "primary_topic": "动态规划与状态设计",
        },
        "2040E": {
            "statement_brief": "树上机器人从 v!=1 出发，第奇数步必向根走；第偶数步可花 1 枚硬币强制向根走，否则随机走向一个邻点。多次询问 f(v,p)：最优用 p 枚硬币时到根的最小期望步数。",
            "transformed_statement": "把题目先看成：机器人每两层过一个“高度为 2 的块”；花硬币相当于跳过某个块里的随机失败重试，应该优先跳过收益最大的块。",
            "key_observations": [
                "从某个点 v 先上到父亲，再随机走时，若没走到祖父，只会落到 v 的兄弟；兄弟的后续局面完全相同。",
                "所以同一父亲下的兄弟答案相同，一个两层块的无硬币期望代价只取决于兄弟数量。",
                "无硬币时可写出 d[v]=d[祖父]+2*(兄弟数+1)。",
                "在偶数步花硬币会让这个块第一次就通过，等价于省掉兄弟数量带来的重复尝试。",
                "对每个查询，只需看 v 到根路径上对应奇偶层的块，选收益最大的 p 个块删掉。",
            ],
            "solution_brief": "关键观察：期望过程可以按两层一块拆开，硬币就是贪心删除路径上最大的块代价。DFS 时维护根路径上两类深度块的收益集合；离线处理查询 (v,p)，从对应集合取前 p 大收益，从无硬币基准期望里减掉即可。",
            "primary_topic": "树结构",
        },
        "2035E": {
            "statement_brief": "打怪初始伤害 d=0。可花 x 把 d 加 1，但连续加伤害最多 k 次；也可花 y 攻击一次造成当前 d 点伤害。求造成至少 z 总伤害的最小费用。",
            "transformed_statement": "把题目先看成：固定总共加伤害 a 次、攻击 b 次时，最优安排一定是尽量每加满 k 次就攻击一次。",
            "key_observations": [
                "固定 a、b 后，为最大化伤害，能加伤害时就应先加，受 k 限制后形成“加 k 次、攻击一次”的块。",
                "设 c=min(⌊a/k⌋, b)，总伤害为 k*c*(c+1)/2 + a*(b-c)。",
                "固定 a 时伤害随 b 单调，固定 b 时伤害随 a 单调，所以可以二分另一维。",
                "不能枚举到 z；题解证明有效操作都用上时总伤害(a,b)>a*b/2。",
                "因此若总伤害>=z，较小的那一维不超过 √(2z)，只需枚举小的一侧。",
            ],
            "solution_brief": "关键观察：把操作顺序压成两个计数 a、b。枚举 a<=√(2z) 并二分最小 b，再枚举 b<=√(2z) 并二分最小 a，用公式算伤害并更新 a*x+b*y 的最小值。",
            "primary_topic": "数论与同余",
        },
        "2257D": {
            "statement_brief": "面积为 S 的未知整数边长矩形左下角固定在原点。每个询问给矩形 x*y，问其中多少单位格可能落在某个合法百慕大矩形内。",
            "transformed_statement": "把题目先看成：所有合法矩形的右上角正好是 S 的因子对，它们的并集是一条按因子变化的阶梯形区域。",
            "key_observations": [
                "合法矩形只有 a*b=S 的因子对，右上角为 (a,b)。",
                "这些矩形都从原点出发，因此它们的并集 F 是单调下降的阶梯形。",
                "询问答案就是查询矩形与 F 的交面积。",
                "把因子按 x 坐标排序，并预处理阶梯区域从 0 到每个因子位置的前缀面积。",
                "回答询问时，二分找到阶梯边界与查询高度或宽度相交的位置，再拼出完整前缀面积和最后一段矩形面积。",
            ],
            "solution_brief": "关键观察：不是逐个合法矩形求并，而是把所有因子对压成阶梯边界。枚举 S 的因子并排序，预处理相邻因子之间的覆盖高度和前缀面积；每个查询在因子列表上二分，按阶梯区域与 x*y 的交集公式 O(log S) 求答案。",
            "primary_topic": "几何",
        },
        "2248A": {
            "statement_brief": "给含 0 和 1 的二进制串。Alice 先删一个 0，想让最终串字典序最大；Bob 再删一个 1，想让最终串字典序最小。求双方最优后的最终串。",
            "transformed_statement": "把题目先看成：删得越靠前，对字典序影响越早；Alice 和 Bob 的最优位置都由第一次出现决定。",
            "key_observations": [
                "Alice 删除更靠前的 0 一定更优，因为比较两个结果时，第一个不同位置会把 0 变成后面的 1。",
                "因此 Alice 必删原串第一个 0。",
                "删 0 不会改变所有 1 的相对顺序。",
                "Bob 要让串最小，对称地应删除剩余串中的第一个 1，也就是原串的第一个 1。",
            ],
            "solution_brief": "关键观察：博弈没有深层搜索，两个最优动作都是删第一次出现。遍历原串，跳过第一个 0 和第一个 1，输出其余字符即可。",
            "primary_topic": "构造与贪心",
        },
        "2245D2": {
            "statement_brief": "构造长度 n 的整数数组，满足若干限制：o=1 要求 a_i+a_j 非负，o=2 要求 a_i+a_j 为负；困难版限制数量不一定覆盖所有二元组。",
            "transformed_statement": "把题目先看成：如果某个点当前没有负和限制，就可把它放成极大的正数；如果没有非负和限制，就可把它放成极小的负数，然后删除它相关的限制。",
            "key_observations": [
                "D1 的符号和绝对值拓扑序在 困难版不必显式维护。",
                "若 i 已没有 o=2 限制，给 a_i 一个很大的正值就能满足它剩下的所有 o=1 限制。",
                "若 i 已没有 o=1 限制，给 a_i 一个很小的负值就能满足它剩下的所有 o=2 限制。",
                "处理掉 i 后，所有与 i 相关的限制都可以删除，并可能让其他点变成新的最大正数或最小负数候选。",
                "这与拓扑排序类似：队列里放 d1_i=0 或 d2_i=0 的点；若最后还有点没处理，说明限制互相卡死，无解。",
            ],
            "solution_brief": "关键观察：构造顺序比实际数值更重要。维护每个点剩余 o=1/o=2 限制数量；若 d2_i=0，就按当前正数序列给大正值，若 d1_i=0，就给大负值。每弹出一个点删除相关边并更新邻点计数；全部弹出则输出构造，否则 NO。",
            "primary_topic": "构造与贪心",
        },
        "2232F": {
            "statement_brief": "有 n 个煎饼和两个锅。第一锅每分钟熟度加 a，第二锅每分钟加 b；可随时端走第一锅、第二锅前移并放新饼。熟度恰好 k 才算完美，求最多完美煎饼数。",
            "transformed_statement": "把题目先看成：若连续若干煎饼都完美，它们在第一锅停留时间 x_i 必须满足线性递推 a*x_i+b*x_{i-1}=k。",
            "key_observations": [
                "第一张完美煎饼要求 a*x_1=k，之后每张同时经历第二锅和第一锅，得到方程 a*x_i+b*x_{i-1}=k。",
                "若 k 不能被 gcd(a,b) 整除，任何连续方程都无法成立，答案为 0；可先整体除以 gcd。",
                "从第一张开始按递推计算，直到某个 x 不是非负整数，这之前形成一段强制完美前缀。",
                "递推断开后，下一张可以作为不完美分隔符，后面的完美段与前一段独立。",
                "一段能连续完美的最大长度由扩展欧几里得和差分中不断增加的 a、b 幂次整除关系确定；若 k 可被 a+b 整除，则该段可无限延长。",
            ],
            "solution_brief": "关键观察：把煎饼流程转成非负整数线性方程链。先用递推吃掉从第一张开始的强制完美前缀；剩余部分按“最多 v 张完美后需要 1 张分隔”的块计数，v 通过扩展欧几里得检查 (a+b)x + b*a^v*y = k 是否有非负解得到。最终为前缀贡献加上剩余块中除分隔符外的数量。",
            "primary_topic": "数论与同余",
        },
        "2231A": {
            "statement_brief": "构造长度 n 的数组，元素在 1..2n 内，且所有元素本身与所有相邻两项和两两不同。",
            "transformed_statement": "把题目先看成：只要让元素和相邻和落在两个互不相交的集合里，就不需要复杂构造。",
            "key_observations": [
                "取所有奇数 1,3,5,...,2n-1 作为数组元素。",
                "这样每个元素都是奇数，且互不相同。",
                "任意相邻两项和都是偶数，不可能等于任何元素。",
                "相邻和也严格递增，因此彼此不同。",
                "最大元素为 2n-1，满足不超过 2n 的限制。",
            ],
            "solution_brief": "关键观察：用奇偶性把两类数分开。直接输出前 n 个正奇数即可；元素全是奇数，相邻和全是偶数且递增，所以全集合两两不同。",
            "primary_topic": "构造与贪心",
        },
        "2174E2": {
            "statement_brief": "交互题。隐藏数 x 在 1..c 内，每次询问进制 b，若 x<b 返回 -1，否则返回 x 在 b 进制下的数位和；第二版固定 k=3、c=2e9，要求三问内猜出 x。",
            "transformed_statement": "把题目先看成：数位和告诉你 x mod (b-1)，所以每次询问都在扩大已知同余模数；返回 -1 时则说明 x 落在一个小前缀里。",
            "key_observations": [
                "任意进制 b 下，x 与其数位和对 b-1 同余；因此一次有效回答给出 x mod (b-1)。",
                "维护当前已知 x=r mod m 后，只需能区分序列 r,r+m,r+2m,... 中的第几个数。",
                "定义 f(m,k) 表示在任意余数 r 下，用 k 次询问能区分的最大步数范围。",
                "基础情形：f(1,1)=3；对一般 m，一问 b=m+2 可区分 m+1 个候选。",
                "递推时令 s=f(m,k-1)，问 b=(s+1)m；若返回 -1 就在小范围内递归，否则用 CRT 把模数扩成 m*((s+1)m-1)，范围迅速膨胀。",
            ],
            "solution_brief": "关键观察：这题的核心不是猜数，而是设计快速增长的同余信息。预先知道 f(1,2)=35，再按递推得到 f(1,3)>2e9；交互时按同一递推发问，遇到 -1 进入小前缀递归，否则把新余数和旧余数用 CRT 合并，最终唯一确定 x。",
            "primary_topic": "交互",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2156E": {
            "statement_brief": "Hao 和亚历克斯在数组上博弈：Hao 每回合删一个未锁元素，亚历克斯每回合锁一个未锁元素，最后保留锁住的元素。美丽值是保留子序列中后项减前项的最大值，Hao 想最小化，亚历克斯想最大化。",
            "transformed_statement": "把题目先看成：二分目标美丽值 g，判断亚历克斯能否保证最终留下某一对差值至少为 g 的下标。",
            "key_observations": [
                "先看亚历克斯先手的简化博弈：若某个下标 i 至少有两个可配对下标 j 能形成差值 >=g，亚历克斯锁 i 后，Hao 只能删掉其中一个，仍会剩一对。",
                "反过来，如果每个 i 至多只有一个这种 j，Hao 总能删掉亚历克斯当前锁点唯一的威胁配对。",
                "回到原题 Hao 先手，他要先删一个 p，使删完后所有下标的威胁配对数都小于 2。",
                "因此 p 必须覆盖所有当前威胁配对数恰为 2 的下标，否则亚历克斯下一手就能锁住必胜点。",
                "计算每个 i 的威胁配对数只需截断到 3；从左到右维护前三小值、从右到左维护前三大值即可线性判断一个 g。",
            ],
            "solution_brief": "关键观察：二分 g 后，胜负只取决于每个点有 0、1、2、超过 2 个可形成差值 >=g 的搭档。线性求出这些截断计数，再枚举 Hao 首删点是否能让所有计数降到 1 以下；若没有这样的删点，则亚历克斯能保证美丽值至少 g。",
            "primary_topic": "博弈",
        },
        "2135A": {
            "statement_brief": "一个块要求所有元素都等于块长；若数组能由若干块拼接得到则称整齐。给数组 a，求最长整齐子序列长度。",
            "transformed_statement": "把题目先看成：若选择位置 i 作为某个块的结尾，且 a_i=x，那么这个块必须由最近的 x 个值为 x 的位置组成。",
            "key_observations": [
                "设 dp[i] 为前 i 个元素能得到的最长整齐子序列长度，显然 dp 单调不降。",
                "若不选 a_i，则 dp[i]=dp[i-1]。",
                "若选 a_i=x，则最后一个块必须有 x 个 x；为了让前面的 dp 尽量大，应选择这 x 个 x 中最靠右的一组。",
                "因此只需维护每个值最近的 x 个出现位置；当出现次数达到 x 时，用这组最左位置前面的 dp 值加 x 更新。",
                "每个位置只进出一次对应队列，总复杂度线性。",
            ],
            "solution_brief": "关键观察：强制 a_i 进答案时，最后一块的起点唯一选“第 x 个最近的 x”。遍历 i，先继承 dp[i-1]，再把 i 放入值 a_i 的队列；若队列长度达到 a_i，就用队首位置前的最优值加 a_i 更新 dp[i]。",
            "primary_topic": "动态规划与状态设计",
        },
        "2124E": {
            "statement_brief": "给正整数数组。一次操作要选择 0<=b_i<=a_i，且 b 的某个前缀和等于后缀和，然后从 a 中减去 b。要求把 a 全变 0 的最少操作数并输出方案。",
            "transformed_statement": "把题目先看成：总和必须能被分成相等两边；若不存在过半元素，则一定能用不超过两次操作完成。",
            "key_observations": [
                "每次减去的 b 总和必须为偶数，所以数组总和为奇数时无解。",
                "若某个元素大于总和一半，它不可能在任意操作中被另一侧匹配完，因此无解。",
                "若存在某个前缀和正好等于总和一半，整数组本身就是一次合法操作。",
                "否则取跨过半和的位置作为枢轴，把左侧和、枢轴、右侧和压成三元组 x,y,z。",
                "题解把三元组的三步直觉合并成两步：第一步同时削掉左块、枢轴的一部分和右块的一部分，使剩余数组变成一次可直接清空的平衡形态。",
            ],
            "solution_brief": "关键观察：答案只会是 -1、1、2。先判总和奇数或最大值过半；若有前缀正好一半，输出一次原数组。否则找到第一个跨过半和的位置，按题解公式从左块、枢轴和右块拆出第一步 b，剩余部分自然满足某个前缀等于后缀，第二步清空。",
            "primary_topic": "构造与贪心",
        },
        "2084C": {
            "statement_brief": "给两个长度 n 的排列 a、b。一次操作选择两个位置，同时交换 a 中这两位和 b 中这两位；问能否操作至多 n 次，使 a_i=b_{n+1-i}。",
            "transformed_statement": "把题目先看成：每个位置的二元组 (a_i,b_i) 只能整体换位置，不能拆开；最终镜像位置必须放互换后的二元组。",
            "key_observations": [
                "操作只是在重排二元组 (a_i,b_i)。",
                "若最终位置 i 放 (x,y)，镜像位置 n+1-i 必须放 (y,x)。",
                "因此每个非自反二元组都必须有对应的反向二元组，否则无解。",
                "若 n 为奇数，必须且只能有一个 a_i=b_i 的自反二元组，它要放到中间；若 n 为偶数则不能有自反二元组。",
                "构造时维护每个值在 a 中的位置，逐个把 b_i 对应的二元组交换到镜像位置即可。",
            ],
            "solution_brief": "关键观察：不是分别改 a、b，而是重排二元组。先检查所有 (x,y) 都有 (y,x)，并处理奇偶中心条件；然后从左到右处理前半段，把当前 b_i 所在的二元组换到 n+1-i，记录交换并同步更新位置表。",
            "primary_topic": "构造与贪心",
        },
        "2077C": {
            "statement_brief": "给二进制串 s，多次翻转某一位。每次翻转后，要求所有非空子序列的分数总和；子序列分数由某个切分点左右两段的 F 值乘积最大值定义。",
            "transformed_statement": "把题目先看成：一个二进制串的分数其实只由 0 和 1 的数量差决定；所有子序列求和后又只依赖当前 0 的数量。",
            "key_observations": [
                "把 0 看作 -1、1 看作 +1，单个二进制串的最优切分分数可化为 ⌊(cnt0-cnt1)/2⌋*⌈(cnt0-cnt1)/2⌉。",
                "统计所有子序列时，只需知道子序列的取值和 i 出现多少次。",
                "换一个视角：未选的 0 贡献 1、选中的 0 贡献 0 后，和为 i 的子序列数变成 C(n, i+cnt0)。",
                "把二次项求和展开，可以得到闭式 2^(n-4)*(n(n+1)-4*cnt0*n+4*cnt0^2-2)。",
                "一次翻转只会让 cnt0 加一或减一，因此每个询问 O(1) 更新答案。",
            ],
            "solution_brief": "关键观察：不要真的枚举子序列或做卷积。维护当前 0 的个数 cnt0；每次翻转后把 cnt0 更新，再代入题解化简出的闭式，在模 998244353 下计算即可。",
            "primary_topic": "组合计数与概率",
        },
        "2063E": {
            "statement_brief": "给根为 1 的树。对任意互不为祖先的点对 (u,v)，令 f(u,v) 为能与两段到 LCA 的距离组成非退化三角形的整数边长数量；求所有点对 f 的总和。",
            "transformed_statement": "把题目先看成：若两条已知边长为 a<=b，可选第三边数量是 2a-1，所以 f(u,v)=2*min(两侧到 LCA 的距离)-1。",
            "key_observations": [
                "三角形不等式给出 b-a < x < a+b，整数 x 正好有 2a-1 个。",
                "对好点对，f(u,v)=2*min(depth_u,depth_v)-2*depth_lca-1。",
                "第一部分 2*min(depth_u,depth_v) 可按较浅点贡献：点 u 贡献给所有深度不小于它且不在其子树内的点。",
                "同深度点对会被两边各算一次，需要按深度组合数扣掉重复。",
                "第二部分 2*depth_lca+1 可按 LCA=w 计数：不同儿子子树之间任选两个后代，用子树大小一次性求和。",
            ],
            "solution_brief": "关键观察：把 f 拆成深度最小值贡献和 LCA 贡献。一次 DFS 求深度、子树大小和每层数量；用深度后缀和统计每个点作为较浅端的贡献，再按每个节点的儿子子树大小统计以它为 LCA 的点对数，套题解公式 O(n) 求总和。",
            "primary_topic": "树结构",
        },
        "2062C": {
            "statement_brief": "给序列 a，可反复执行反转或替换为相邻差分序列，直到长度为 1 前都可继续。求所有操作后序列元素和的最大可能值。",
            "transformed_statement": "把题目先看成：反转操作只影响后续差分的符号；任意操作序列等价于先做若干次差分，再决定是否整体取反。",
            "key_observations": [
                "比较相邻操作“先反转再差分”和“先差分再反转”，二者结果只差一个整体负号。",
                "所以所有反转都可以交换到差分之后，交换过程中只记录是否取反。",
                "反转本身不改变当前序列和。",
                "因此做过至少一次差分后，当前和的正负都可实现，贡献看绝对值。",
                "若一次差分都不做，则不能凭空取反，只能保留原始和。",
            ],
            "solution_brief": "关键观察：只枚举差分次数。先用原数组和初始化答案；然后不断把数组替换成相邻差分，计算当前和的绝对值更新答案。数值上界可到 1000*2^50，需要 64 位整数。",
            "primary_topic": "构造与贪心",
        },
        "2059A": {
            "statement_brief": "给两个好数组 a、b，好数组表示每个出现过的值至少出现两次。可以任意重排 a，令 c_i=a_i+b_i，问能否让 c 至少有 3 个不同值。",
            "transformed_statement": "把题目先看成：只关心两个数组各自有多少种不同值，而不关心具体频次；好数组条件保证需要的值能重复取到。",
            "key_observations": [
                "若某个数组已有至少 3 个不同值，配上另一个数组中任意三个元素并按大小安排，和也能得到至少 3 种。",
                "若两个数组都恰好有 2 个不同值，设一边为 x<y、另一边为 a<b，可以得到 x+a < x+b < y+b 三个和。",
                "好数组条件保证较小值等需要的元素至少出现两次，不会因为取样次数不够失败。",
                "剩余情况中，一个数组只有 1 种值，另一个数组至多 2 种值，和的种类最多也只有 2。",
            ],
            "solution_brief": "关键观察：答案等价于两边不同值个数之和至少为 4。统计两个数组不同值个数，和至少为 4 输出 YES，否则 NO。",
            "primary_topic": "构造与贪心",
        },
        "2056D": {
            "statement_brief": "定义数组排序后的两个中位数相等时为好数组；奇数长度自动满足。给值域 1..10 的数组，求好子数组数量。",
            "transformed_statement": "把题目先看成：总子数组数减去坏子数组数；坏子数组一定是偶数长度且两个中位数不相等。",
            "key_observations": [
                "固定坏子数组的较小中位数为 x，把 a_i<=x 记为 -1，否则记为 +1。",
                "偶长子数组以 x 为较小中位数且不是好数组，当且仅当这段新数组和为 0，并且原段里出现过 x。",
                "和为 0 已经自动排除了奇数长度，所以不需要另判长度奇偶。",
                "值域只有 10，可以枚举 x。",
                "扫描时只在遇到 a_i=x 后，才把此前前缀和加入计数，确保统计的区间包含 x。",
            ],
            "solution_brief": "关键观察：坏区间可转成前缀和相等。对每个 x=1..10 建 b：<=x 为 -1，>x 为 +1；从左到右维护前缀和出现次数，只有经过某个 x 的位置才开放左端，累计和为 0 且含 x 的区间数。总子数组数减去所有坏区间即答案。",
            "primary_topic": "数据结构",
        },
        "2039F1": {
            "statement_brief": "对数组 a，f(k) 是所有长度 k 子数组最大值的 gcd。若所有 f(k) 两两不同，则数组合格。给 m，统计任意长度、元素在 1..m 的非空合格数组数量。",
            "transformed_statement": "把题目先看成：长度 k+1 的子数组最大值序列来自长度 k 的相邻最大值，因此对应 gcd 会形成严格整除链。",
            "key_observations": [
                "设 s_k 为长度 k 子数组最大值序列、g_k 为 s_k 的 gcd，则 s_{k+1} 每个元素都被 g_k 整除，所以 g_k | g_{k+1}。",
                "合格要求所有 g_k 不同，因此 g_k 必须沿整除关系严格变大，长度最多为 ⌊log2 m⌋+1。",
                "若先考虑严格递增的值序列，则长度 k 的最大值只来自后缀，条件变成所有后缀 gcd 互不相同。",
                "一个满足条件的递增值序列可产生 2^(n-1) 个合格排列：从最大值往小值插入时，每次只能放在相邻较大值的左边或右边。",
                "计数递增序列时，状态可用当前起点和后缀 gcd；用“按倍数汇总再对因子做容斥”得到精确 gcd 转移。",
            ],
            "solution_brief": "关键观察：先把任意数组规约为递增值集合加插入方式。枚举可行长度；用 DP 统计严格递增序列且后缀 gcd 严格变化的数量，转移时通过每个 i 的因子集合做容斥求 gcd(i,h) 的精确贡献，最后乘 2^(长度减一) 汇总。",
            "primary_topic": "数论与同余",
        },
        "2035B": {
            "statement_brief": "给长度 n，要求构造只含数字 3 和 6 的最小十进制整数，使它同时被 33 和 66 整除；不存在则输出 -1。",
            "transformed_statement": "把题目先看成：被 66 整除等价于被 2、3、11 整除；末位必须是 6，而字典序越小数字越小。",
            "key_observations": [
                "若已有某个长度的最小合法数，在前面加 33 可得到长度加 2 的最小合法数。",
                "加在最前面的 33 比把 6 提前更优，因为十进制数先比较高位。",
                "长度 2 的最小答案是 66。",
                "长度 1 和 3 无解；长度 5 的最小答案是 36366。",
                "因此偶数长度在前面补 n-2 个 3 再接 66，奇数长度至少 5 时在前面补 n-5 个 3 再接 36366。",
            ],
            "solution_brief": "关键观察：只需记住两个基础串。n 为偶数输出 3*(n-2)+66；n 为 1 或 3 输出 -1；其余奇数输出 3*(n-5)+36366。",
            "primary_topic": "构造与贪心",
        },
        "2005E2": {
            "statement_brief": "困难版矩阵子序列博弈：两人按数组 a 的顺序在矩阵 b 中选等值格子；每次选 (r,c) 后，下一人只能在右下子矩阵继续，不能行动者输。判断先手胜负。",
            "transformed_statement": "把题目先看成：同一个目标值的很多格子会互相支配；真正需要保留的是那些“尽量靠右下、不给对手更多空间”的前沿格子。",
            "key_observations": [
                "简单版可从后往前做极小极大：当前位置赢，当且仅当其右下方没有下一层的赢位置。",
                "困难版不能对每一层扫描整个矩阵。",
                "同值格子中，若一个格子比另一个更靠右下，选择更靠右下只会缩小对手后续可选区域，不会变差。",
                "因此每个目标值只保留非支配前沿；题解提示中样例的可选 2 只剩反对角线上的几个格子。",
                "对数组 a 中出现的值和每一列，预处理该值在此列能取到的最大行，就能在这些前沿索引上推进博弈。",
            ],
            "solution_brief": "关键观察：把矩阵格子先按支配关系压缩，再做简单版同样的倒推。忽略 a 中没出现的值；对每个相关值、每列记录最大行，形成可选前沿。随后从 a 的末尾往前维护下一层赢点能覆盖哪些右下区域，判断当前层是否存在必胜前沿格。",
            "primary_topic": "博弈",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2255E1": {
            "statement_brief": "数组初始给定，区间操作会产生历史版本；查询某个位置 p 时，要看所有历史版本中该位置的值序列，并求其中最大非空子数组和。简单版值始终只可能是 -1、0、1。",
            "transformed_statement": "把题目先看成：每个位置独立产生一条历史序列，区间操作只是给一段位置追加同一类“状态变换 + 历史片段”。",
            "key_observations": [
                "固定一个位置，历史值序列只需要维护总和、最大前缀、最大后缀和最大非空子段和。",
                "值域只有 -1、0、1，因此一段操作 T 可以对每个初始值 s 预存最终值 f_T(s) 和执行期间产生的历史摘要 H_T(s)。",
                "两段操作拼接时，最终值按函数复合，历史摘要按前段历史加后段在新状态下的历史拼接，所以懒标记闭合。",
                "区间更新只把这些常数大小的操作摘要复合到线段树节点上，不需要立刻下推到每个位置。",
                "查询某个点时沿根到叶物化它自上次查询后的新增历史，再用旧最大后缀和新最大前缀拼出跨段答案。",
            ],
            "solution_brief": "关键观察：把“很多版本的点值”压成可拼接的最大子段摘要。线段树节点存一段未下推操作的三状态变换；区间更新复合标记，点查询时才下推并合并该点历史。type-4 要先回答截至上一版本的历史，再记录当前版本。",
            "primary_topic": "数据结构",
        },
        "2248E": {
            "statement_brief": "给周期长度、若干奖励点和连续 1 的基础收益。二进制串中连续 1 段按长度产生收益，0 会重置计数；问是否存在某个二进制串比同长度全 1 串收益更高。",
            "transformed_statement": "把题目先看成：插入 0 的唯一作用是把一个长全 1 段拆成多个短段，因此只需判断拆成两段是否能带来正收益。",
            "key_observations": [
                "记 S_i 为长度 i 的全 1 串收益；因为计数到 n 重置，有 S_{i+n}=S_i+S_n。",
                "若存在 x,y 使 S_x+S_y>S_{x+y+1}，那么串 1^x 0 1^y 已经严格优于同长度全 1 串。",
                "反过来，若所有 x,y 都不满足这个不等式，则任意多段串都可按首段归纳证明不可能赢。",
                "所以答案完全由 M=max(S_x+S_y-S_{x+y+1}) 是否大于 0 决定。",
                "这个最大值只会在 x、y 取奖励点位置时达到；周期公式配合双指针即可检查所有奖励点对。",
            ],
            "solution_brief": "关键观察：不要枚举所有二进制串，只判断“一个 0 把长段拆成两段”是否有收益。预处理全 1 串收益 S，枚举奖励点 p_i,p_j，若 S_{p_i}+S_{p_j}>S_{p_i+p_j+1} 就输出 YES，否则 NO。",
            "primary_topic": "组合计数与概率",
        },
        "2247F": {
            "statement_brief": "在有障碍的网格中，路径只能向右或向下。一个非空格子集合 S 为 good，当且仅当任意经过 S 中某个格子的完整路径都会经过 S 中所有格子；要求计数 good 集合。",
            "transformed_statement": "把题目先看成：两个格子能放进同一个 good set，等价于它们被完整路径强制一起经过；这种强制关系可以建成有向图并取强连通分量。",
            "key_observations": [
                "若集合中有一个没有任何完整路径经过的空格，那么集合中其他格子也必须全是这种格子，先贡献 2^free-1。",
                "对至少在一条完整路径上的格子，两个格子若不可按左上到右下偏序比较，就不可能被同一条单调路径同时经过。",
                "若 A 在 B 的左上方，想把 A 和 B 放进同一集合，就必须所有起点到 B 的路径都经过 A；右下方向同理。",
                "把“经过当前格子的完整路径必经过另一个格子”连成有向边后，good set 正好是同一强连通分量内的任意非空子集。",
                "实际建图时只需找每个格子两个方向上的最近强制祖先，用反对角线处理和并查集合并互相强制的格子。",
            ],
            "solution_brief": "关键观察：good set 不是任意路径交集，而是“完整路径必经关系”的强连通分量。先统计完全不在任何完整路径上的格子；其余格子用起点侧和终点侧的强制经过关系合并 SCC，每个分量贡献 2^{大小}-1。",
            "primary_topic": "图论与网络流",
        },
        "2238E": {
            "statement_brief": "给由 T、F、N 组成的串，N 可由 GLaDOS 改成 T 或 F。之后 Chell 选择一段连续区间作为假蛋糕段，错误数由真实串和选择区间决定；求 GLaDOS 能保证的最大错误数。",
            "transformed_statement": "把题目先看成：固定最终串后，Chell 的最优选择就是在一个 +1/-1 数组里取最大子段和。",
            "key_observations": [
                "若 F 记为 +1、T 记为 -1，选择区间内的 F_in-T_in 就是该区间和。",
                "固定最终串时，Chell 最小化错误等价于最大化所选区间和，因此最小错误为 F_total-S_max。",
                "GLaDOS 的目标变成在替换所有 N 后最大化 F_total-S_max。",
                "从左到右 DP 时，只需记录已放 F 的数量 f、当前最大非负后缀和 s，以及全局最大子段和的最小可行值。",
                "放 F 会让后缀和加一并可能更新全局最大；放 T 会让后缀和减一但不低于零。",
            ],
            "solution_brief": "关键观察：先把区间选择转成最大子段和，再对未知字符做 DP。状态 dp[i][f][s] 表示前 i 位、用了 f 个 F、当前最大非负后缀为 s 时，全局最大子段和的最小值；最后取 max(f-dp[n][f][s])。",
            "primary_topic": "动态规划与状态设计",
        },
        "2238C": {
            "statement_brief": "树以 1 为根。对每个中心 v 和距离 h，v 子树中距离 v 恰好 h 的点集构成一个 guild；要求统计不同的非空 guild 数量。",
            "transformed_statement": "把题目先看成：子树内部已有的 guild 交给儿子统计，中心正好是当前点 v 的新 guild 只取决于儿子子树能延伸多深。",
            "key_observations": [
                "每个点 v 自己对应 h=0 的 guild，固定贡献 1。",
                "若某个 h 层的点全部来自同一个儿子子树，这个 guild 已经会在该儿子的答案中出现。",
                "真正以 v 为中心的新 guild，必须在至少两个儿子子树里都能取到距离 h 的点。",
                "令 L_to 为儿子 to 的子树从 v 往下能达到的最大距离；满足至少两个 L_to>=h 的 h 数量正好等于第二大的 L_to。",
                "因此 ans_v=1+第二大延伸深度+所有儿子 ans 之和。",
            ],
            "solution_brief": "关键观察：每个点的新贡献不是最大深度，而是第二大儿子深度。DFS 求每个子树最大深度；回溯时取当前点所有儿子的两个最大 L，按 ans_v=1+second_max+sum(ans_child) 计算即可。",
            "primary_topic": "树结构",
        },
        "2226F": {
            "statement_brief": "数组 a 初始全 0，每次把一个位置限制为某个 x|n。合法排列 p 要满足每个位置要么无限制，要么 gcd(p_i,n)=a_i；每次更新后求所有合法排列的逆序数总和。",
            "transformed_statement": "把题目先看成：先按 gcd 值分组数合法排列数，再用 x 和 n-x 的对称性一次性求低于 n 的所有逆序贡献。",
            "key_observations": [
                "对 1<=x<n，有 gcd(x,n)=gcd(n-x,n)，所以把所有低于 n 的值整体替换为 n-x 仍满足同一组限制。",
                "在这种互补配对中，低于 n 的任意一对值的逆序和非逆序会完全互换。",
                "因此低于 n 的值平均逆序贡献固定为 1/2*C(n-1,2)，不需要逐位置统计。",
                "对每个约数 d，只需维护要求 gcd 等于 d 的位置数 cur_d，以及可用值数量 cnt_d；若 cur_d>cnt_d 则无解。",
                "值 n 要单独处理：若 n 被固定在某个位置，它贡献右侧位置数；否则它可放在任意未限制位置，贡献对这些位置求和。",
            ],
            "solution_brief": "关键观察：逆序和的难点被 gcd 补数对称性消掉。维护每个 gcd 组的排列数乘积 B、未限制位置数 Z，以及 n 是否已固定；套题解的两种公式计算低于 n 的平均贡献加上 n 的位置贡献，每次更新 O(1) 或按约数维护。",
            "primary_topic": "数论与同余",
        },
        "2223D": {
            "statement_brief": "有向图中每个点 i 能连向所有 j>=a_i 的点。要求构造一个哈密顿环，或判断不存在。",
            "transformed_statement": "把题目先看成：把哈密顿环的边 i->u_i 拆成固定边 i->a_i 和补边 a_i->u_i，问题转为给固定有向图补若干从小到大的边，使其存在欧拉回路。",
            "key_observations": [
                "固定边 i->a_i 已经确定；若能补边把每个点出入度配平且图连通，就能从欧拉回路还原哈密顿环。",
                "补一条 u<v 的边会让 deg_u 加一、deg_v 减一，其中 deg=出度-入度。",
                "所有 deg 能被这种边配平，当且仅当前缀和始终不大于 0。",
                "前缀和等于 0 的位置是不可跨越的切点；任何补边跨过去都会破坏度数可行性。",
                "先在每个切点区间内加相邻边保证可连通，再按正负度差贪心配平，最后跑欧拉回路。",
            ],
            "solution_brief": "关键观察：哈密顿环被转成欧拉补边问题。先建固定边并算 deg 前缀和，若某个前缀为正则无解；按前缀和为 0 的切点分块，在块内检查连通并补相邻边，再用贪心把度差清零，欧拉回路中相邻固定边和补边即可还原答案。",
            "primary_topic": "图论与网络流",
        },
        "2223A": {
            "statement_brief": "给两个等长括号串 a、b。每个位置可以选择是否交换 a_i 和 b_i，问能否让两个串都变成合法括号序列。",
            "transformed_statement": "把题目先看成：a_i=b_i 的位置无法改变；只有 a_i!=b_i 的位置需要决定哪一串拿左括号。",
            "key_observations": [
                "相同位置交换与否都一样，可以忽略。",
                "不同位置中，a 拿到左括号的次数必须正好是一半；b 自动拿到另一半。",
                "合法括号串的核心条件是每个前缀左括号数不少于右括号数，且总数平衡。",
                "从左到右让不同位置在 a 中交替放左、右括号，就等价于每次优先修正当前前缀平衡。",
                "构造后再同时检查 a 和 b 的前缀平衡即可，失败则无解。",
            ],
            "solution_brief": "关键观察：只需要处理 a_i!=b_i 的位置。按出现顺序把这些位置奇数个给 a 放 '('、偶数个给 a 放 ')'，b 取相反字符；最后检查两个串是否都是合法括号序列。",
            "primary_topic": "构造与贪心",
        },
        "2207A": {
            "statement_brief": "给二进制串。一次操作可选择左右相邻都是 1 的中间位置，并把它改成 0 或 1；可操作任意次，求最终 1 的最少和最多数量。",
            "transformed_statement": "把题目先看成：操作只能在由 1 和夹在两个 1 中间的单个 0 组成的连通块里传播，两个相邻 0 会永久隔断。",
            "key_observations": [
                "与另一个 0 相邻的 0 永远不可能变成 1，因为它无法同时拥有左右两个 1。",
                "操作也不可能制造相邻的两个 0，因为能改成 0 的位置两侧当时都是 1。",
                "因此原串被相邻 0 隔成若干独立块，每块内部的 1 可以通过填单个 0 连成一段。",
                "最大值时，把每个这种块能填的孤立 0 都变成 1。",
                "最小值时，在块内尽量隔一个删一个 1，最多能制造 floor((L-1)/2) 个 0。",
            ],
            "solution_brief": "关键观察：相邻 0 是不可跨越的墙。扫描所有由若干段 1、且段间只隔一个 0 连接成的块；最大 1 数把块内全部变成 1，最小 1 数从块长里扣掉可制造的 floor((L-1)/2) 个孤立 0，再加上原本被墙隔开的部分。",
            "primary_topic": "构造与贪心",
        },
        "2191B": {
            "statement_brief": "给数组，可任意重排。要求对每个切分点，前缀的 MEX 和后缀的 MEX 都不同；问是否存在这样的重排。",
            "transformed_statement": "把题目先看成：一个区间的 MEX 是否大于 0 只取决于它是否含有 0；MEX 是否等于 1 还取决于它是否不含 1。",
            "key_observations": [
                "如果数组没有 0，任意前缀和后缀的 MEX 都是 0，必然失败。",
                "如果只有一个 0，把它放在最后，则任意真前缀不含 0，后缀含 0，二者 MEX 不同。",
                "若至少两个 0 且没有 1，总能在两个 0 之间切一刀，让两边都含 0 且都不含 1，MEX 都为 1。",
                "若至少两个 0 且存在 1，把所有 1 放在所有 0 前面；含 0 的前缀也会含 1，所以前缀 MEX 至少为 2。",
                "此时后缀若只剩 0，则 MEX 为 1；若还没碰到 0，前缀 MEX 为 0，仍不同。",
            ],
            "solution_brief": "关键观察：答案只看 0 和 1 的数量。若 cnt0=0 输出 NO；若 cnt0=1 输出 YES；若 cnt0>=2，则 cnt1>0 才能把所有 0 放末尾避免两侧 MEX 同为 1。",
            "primary_topic": "构造与贪心",
        },
        "2154C1": {
            "statement_brief": "简单版所有操作代价都为 1。每次可把某个 a_i 加一，求最小总代价，使数组中存在一对数的 gcd 大于 1。",
            "transformed_statement": "把题目先看成：答案只可能是 0、1、2；因为任选两个数都能各加至偶数。",
            "key_observations": [
                "任意整数至多加一就能变成偶数，所以两个元素总能用不超过两次操作得到公共因子 2。",
                "答案为 0 当且仅当当前已有两个元素共享某个质因子。",
                "只需要检查公共质因子，不需要枚举所有合数约数。",
                "答案为 1 时，存在某个 i，使 a_i+1 的某个质因子已经出现在其他元素中。",
                "预处理每个数的不同质因子后，先统计当前质因子出现次数，再逐个临时移除 a_i 的贡献检查 a_i+1。",
            ],
            "solution_brief": "关键观察：先用“最多两次变偶数”把答案范围压到 0/1/2。筛出质因子；若某个质因子在两个 a_i 中出现，答案 0。否则枚举 i，移除 a_i 的质因子后检查 a_i+1 是否与剩余元素共享质因子，有则答案 1，否则答案 2。",
            "primary_topic": "数论与同余",
        },
        "2153A": {
            "statement_brief": "苹果树围成环，每个苹果有美味值。你可以无限绕圈，只有当前苹果美味值严格大于上一次吃的苹果时才能吃；求最多能吃多少个。",
            "transformed_statement": "把题目先看成：时间不是限制，因为可以绕很多圈；真正限制只有吃到的美味值必须严格递增。",
            "key_observations": [
                "同一个美味值最多吃一个，因为之后再遇到相同值不再严格更大。",
                "因此答案不可能超过不同美味值的数量。",
                "这个上界总能达到：把所有不同值按从小到大排序。",
                "第 i 次绕完整个环时，选择吃一个值为第 i 小美味值的苹果即可。",
                "位置顺序不重要，因为每一轮都能重新从环上经过所有树。",
            ],
            "solution_brief": "关键观察：环和无限时间让位置约束消失，只剩严格递增值约束。统计数组中不同美味值个数并输出即可。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2118D1": {
            "statement_brief": "一条长度 10^15 的路上有 n 个红绿灯，第 i 个灯在时间 t≡d_i (mod k) 时为红灯。人从查询位置出发、初始向正方向走；每秒先看当前位置红灯则掉头，再走一步，问是否会在 10^100 秒内离开路段。",
            "transformed_statement": "把题目先看成：运动只在红绿灯位置可能改变方向；若本地题解正文缺失，不能可靠提炼有限状态图上的判环细节。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只清理题意和转换视角，保留原题链接与题解链接，避免根据旧总结或宽标签补写。",
            "extraction_status": "missing_editorial",
            "primary_topic": "图论与网络流",
        },
        "2118A": {
            "statement_brief": "要求构造一个长度为 n、恰好含 k 个 1 的二进制串，使其中子序列 101 和 010 的数量相等。",
            "transformed_statement": "把题目先看成：不必精确计数任意串的两类子序列，只要构造出两类子序列都为 0 的串即可。",
            "key_observations": [
                "若所有 1 都在所有 0 的前面，串中不会出现 101，因为 0 之后没有新的 1。",
                "同样也不会出现 010，因为 1 之前没有 0，且 0 后没有 1。",
                "两类目标子序列数量都为 0，自然相等。",
                "这个排列方式还能直接控制 1 的数量：先放 k 个 1，再放 n-k 个 0。",
            ],
            "solution_brief": "关键观察：把构造目标降到“让两种子序列都不存在”。直接输出 k 个 1 后接 n-k 个 0；此时 101 和 010 都无法作为子序列出现。",
            "primary_topic": "构造与贪心",
        },
        "2115D": {
            "statement_brief": "每轮当前玩家在 a_i 和 b_i 中选一个异或到 x；Gellyfish 想最小化最终 x，Flower 想最大化最终 x。给所有轮次的操作者，求双方最优后的最终值。",
            "transformed_statement": "把题目先看成：默认所有轮都选 a_i，则初值变成 a 的异或和；第 i 轮改选 b_i 只相当于额外异或一个差分向量 a_i⊕b_i。",
            "key_observations": [
                "每个操作都是异或加法，所以整局是若干差分向量是否被选择的线性空间博弈。",
                "从后往前看，未来轮次对当前 x 的影响可以用一组消元后的异或线性基表示。",
                "若当前差分向量已被未来线性基张成，它不会产生新的最高决定位，对最优结果没有独立控制权。",
                "若它是新基向量，其最高位将由当前轮的玩家控制：最大化玩家希望该位为 1，最小化玩家希望该位为 0。",
                "最后把默认初值用这组基约简，再把属于最大化玩家控制的新基向量异或回去，就得到博弈值。",
            ],
            "solution_brief": "关键观察：把逐轮选 a/b 改写成 XOR 线性基上的后缀博弈。从后往前插入 a_i⊕b_i，只有线性无关的向量会留下一个可控制的最高位，并记录它属于哪位玩家；最后按这些控制权恢复最优最终 x。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2040B": {
            "statement_brief": "长度 n 的全 0 数组。一次一类操作可把单个 0 变 1；一次二类操作可选择两端为 1 且 1 的数量不少于区间一半的区间，并把整个区间变 1。求最少需要多少次一类操作。",
            "transformed_statement": "把题目先看成：一类操作负责播种新的 1，二类操作负责把已有 1 的密度扩张成更长的连续 1 段。",
            "key_observations": [
                "任意时刻数组中的 1 形成若干不相交连续段。",
                "一类操作最多让连续段数量加一；二类操作若覆盖 x 段，会让段数减少 x-1。",
                "因此二类操作次数不可能超过一类操作次数减一。",
                "最优策略是一开始放一个 1，之后每次再放一个 1，并用一次二类操作把当前可覆盖长度从 x 扩到 2*(x+1)。",
                "于是 k 次一类操作最多覆盖的长度满足 f_1=1、f_k=2*(f_{k-1}+1)。",
            ],
            "solution_brief": "关键观察：只需要模拟最优扩张长度。令 covered=1、ans=1；当 covered<n 时，再做一次一类操作并接一次二类扩张，使 covered=2*(covered+1)，直到覆盖 n。",
            "primary_topic": "构造与贪心",
        },
        "2039A": {
            "statement_brief": "构造一个递增整数序列 a_1..a_n，范围在 1..100 内，使所有 a_i mod i 两两不同。",
            "transformed_statement": "把题目先看成：第 i 个余数的可选范围只有 0..i-1；若要 n 个余数全不同，就自然让 a_i mod i=i-1。",
            "key_observations": [
                "a_1 mod 1 固定为 0，所以 a_2 mod 2 不能再为 0，只能为 1。",
                "依次类推，a_i mod i 必须取此前没出现过的最大余数 i-1。",
                "又要求序列递增，所以 a_i 至少要不小于 i。",
                "取 a_i=2i-1 时，既有 a_i mod i=i-1，又得到严格递增奇数序列。",
                "n<=50 时最大值 2n-1<=99，满足上界 100。",
            ],
            "solution_brief": "关键观察：把不同余数直接钉成 0,1,...,n-1。输出 1,3,5,...,2n-1；第 i 项对 i 取模正好是 i-1，因此所有余数两两不同。",
            "primary_topic": "构造与贪心",
        },
        "2034F2": {
            "statement_brief": "抽红蓝宝石直到箱子为空；经过某些指定剩余数量状态时，已经装进袋子的宝石价值整体翻倍。求最终袋子价值的期望。",
            "transformed_statement": "把题目先看成：抽取顺序是一条从 (0,0) 到 (n,m) 的格路；卷轴条件可改写成格路上的若干特殊点，经过特殊点会让此前贡献多乘一个 2。",
            "key_observations": [
                "把“箱子剩余 r,b”改成“袋子已有 n-r,m-b”，所有条件点就落在从起点到终点的单调格路上。",
                "两点之间不考虑特殊限制的路径数是组合数 C(dx+dy,dx)。",
                "一条路径若经过 c 个特殊点，翻倍因子 2^c 可以理解为从这些特殊点集合中任选子集的计数。",
                "因此不用显式枚举经过了几个卷轴，而是倒序计算每个特殊点到终点的加权路径数 weight_i。",
                "点 i 对答案的贡献是到达它的路径数、从它到终点的加权路径数，以及当时袋中价值 2x_i+y_i 的乘积。",
            ],
            "solution_brief": "关键观察：用“经过特殊点的子集数”替代 2 的幂。排序所有特殊点并预处理组合数；倒序求 weight_i=sum paths(i,j)*weight_j，再累加 (2x_i+y_i)*paths(0,i)*weight_i，最后除以总路径数 C(n+m,n)。",
            "primary_topic": "组合计数与概率",
        },
        "2028B": {
            "statement_brief": "数组由 n,b,c 定义：a_i=b*(i-1)+c。每次把当前最大值的最左出现替换为数组 MEX，问首次变成 0..n-1 的排列需要几次；若永远不行输出 -1。",
            "transformed_statement": "把题目先看成：当 b>0 时原数组元素互不相同，每次操作只是在把一个超出范围的值换成缺失的小值。",
            "key_observations": [
                "若 b>0，数组始终保持元素互异；只要最大值仍不小于 n，就还不是合法排列。",
                "此时需要替换的次数就是初始数组中不在 0..n-1 内的元素个数。",
                "这个个数可由最大满足 b*(i-1)+c<n 的下标直接算出。",
                "若 b=0，所有元素都等于 c，需要单独讨论重复值如何被 MEX 逐个替换。",
                "b=0 时 c>=n 需要 n 次；c 为 n-1 或 n-2 时需要 n-1 次；更小的 c 会进入循环，无法成为排列。",
            ],
            "solution_brief": "关键观察：分开处理常数数组和严格等差数组。b=0 按 c 与 n 的关系套三种结论；b>0 时计算已有多少项落在 [0,n-1]，答案就是 n 减去这个数量。",
            "primary_topic": "构造与贪心",
        },
        "2245C": {
            "statement_brief": "构造 0..n-1 的排列 p。令 f(i) 为前缀 p_0..p_i 的 MEX，要求所有前缀 MEX 的异或和等于 k，或判断无解。",
            "transformed_statement": "把题目先看成：最后一个前缀的 MEX 恒为 n，所以只需控制前 n-1 个前缀 MEX 的异或为 k⊕n。",
            "key_observations": [
                "把 0 放得越靠后，前面大量前缀的 MEX 都会固定为 0。",
                "若目标 K'=k⊕n 为 0，把 0 放最后即可。",
                "若 1<=K'<=n-1，把 0 放倒数第二、K' 放最后，则倒数第二个前缀 MEX 正好为 K'。",
                "若 K'>n-1，不能用单个 proper prefix 的 MEX 表示，只能尝试拆成 v 和 n-1 两个 MEX。",
                "当 K' 与 n-1 最高位不同，无论怎样异或不超过 n-1 的 MEX 都造不出该最高位；否则取 v=(n-1)⊕K' 并把末尾构造成 0,v,n-1。",
            ],
            "solution_brief": "关键观察：通过控制 0 的位置，让几乎所有前缀 MEX 归零，只在末尾制造一到两个需要的 MEX。先设 K'=k⊕n，按 K'=0、K'<=n-1、否则用 v=(n-1)⊕K' 三类构造；最高位不匹配则输出 NO。",
            "primary_topic": "构造与贪心",
        },
        "2215A": {
            "statement_brief": "给数组 a、长度下限 k 和两个模数 p<q。一次操作可选长度至少 k 的区间并把其中元素对 p 或 q 取模，操作任意次；求最终数组和的最小值。",
            "transformed_statement": "把题目先看成：每个位置最终只会在 a_i mod p 和 (a_i mod q) mod p 两个值里选；限制只来自第一次被整体操作的区间。",
            "key_observations": [
                "先对 p 取模后再做其他操作不会比 a_i mod p 更小；先对 q 再对 p 得到另一种可能值。",
                "除第一次选择的区间外，后续操作可以把其他位置各自降到 min(b_i,c_i)。",
                "第一次区间里的所有元素必须同步走同一种第一步，因此只能整体取 sum b 或整体取 sum c 的较小者。",
                "第一次区间取更长不会更优，因为多包含的位置本来可以单独降到 min(b_i,c_i)。",
                "所以只需枚举所有长度恰好为 k 的第一次区间。",
            ],
            "solution_brief": "关键观察：全局操作被压成一个长度 k 的特殊窗口。预处理 b_i=a_i mod p、c_i=(a_i mod q) mod p 和 min 前缀和；枚举窗口 [l,r]，答案为窗口外 min 之和加 min(窗口 b 和, 窗口 c 和)。",
            "primary_topic": "构造与贪心",
        },
        "2205A": {
            "statement_brief": "给一个排列，定义位置 i 是 ugly 当且仅当 i 等于前缀 p_1..p_i 的最大值。最多交换一次，要求输出 ugly 位置数最少的排列。",
            "transformed_statement": "把题目先看成：最后一个位置 n 永远 ugly，因为整个排列最大值必为 n；目标是让其他位置都不 ugly。",
            "key_observations": [
                "答案下界至少为 1，因为 i=n 时前缀最大值一定是 n。",
                "若把值 n 放到第一个位置，那么任意 i<n 的前缀最大值都是 n，不可能等于 i。",
                "这样只有最后一个位置可能 ugly，正好达到下界。",
                "最多交换一次足够：找到 n 的位置，把它和第一项交换即可。",
            ],
            "solution_brief": "关键观察：把最大值 n 提到最前面会压住所有前缀最大值。直接交换 p_1 和值 n 所在位置，然后输出排列；此时只有位置 n 是 ugly。",
            "primary_topic": "构造与贪心",
        },
        "2188A": {
            "statement_brief": "构造 1..n 的排列 p，使每个相邻差 |p_i-p_{i+1}| 都能被 i 整除。",
            "transformed_statement": "把题目先看成：最后一对差值必须是 n-1，因此最后两个数只能是 1 和 n；随后可以从后往前逐个倒推。",
            "key_observations": [
                "因为两个排列值都在 1..n 内，|p_{n-1}-p_n| 能被 n-1 整除时，只能等于 n-1。",
                "所以末尾必须放 1 和 n，顺序任选。",
                "从 i=n-2 往前构造时，为了让差值能被 i 整除，只需在 p_{i+1}-i 和 p_{i+1}+i 中选一个。",
                "题解指出每一步在范围内且未使用的可行选择只有一个。",
                "倒序补完后反转得到排列。",
            ],
            "solution_brief": "关键观察：从最苛刻的末尾条件倒推。先令末尾为 1,n；然后 i 从 n-2 到 1，若 p_{i+1}-i 合法且未用就选它，否则选 p_{i+1}+i，最终反转输出。",
            "primary_topic": "构造与贪心",
        },
        "2176A": {
            "statement_brief": "给数组。一次操作可选择 i<j 且 a_i>a_j，并删除 a_j；求最多能执行多少次删除。",
            "transformed_statement": "把题目先看成：一个元素能否被删除，只取决于它左边是否曾出现过严格更大的元素。",
            "key_observations": [
                "第一个元素永远不能删，因为它左边没有元素。",
                "若 a_j 小于此前某个元素，则可以用那个更大的左侧元素删掉它。",
                "删除其他元素不会破坏这个左侧见证，因为相对顺序保留，且见证在它左边。",
                "反过来，若 a_j 不小于此前所有元素，就不存在严格更大的左侧元素，它永远删不掉。",
                "所以不能删除的正是从左到右扫描时的前缀最大值位置。",
            ],
            "solution_brief": "关键观察：保留下来的必须是前缀最大值。扫描数组维护当前最大值；遇到小于当前最大值的元素就计入可删除，否则更新最大值。答案等于可删除元素数量。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2173C": {
            "statement_brief": "给集合 A 中的 n 个数和上界 k。要求找最小集合 B，使 A 中每个数都有一个来自 B 的因子，且 B 中每个数在 1..k 内的所有正倍数都必须出现在 A 中；无解输出 -1。",
            "transformed_statement": "把题目先看成：每次从 A 里还没被覆盖的最小数开始，它若想被覆盖，就只能自己进入 B。",
            "key_observations": [
                "设当前未完成元素中最小的是 x，它在 A 中没有更小的可用因子能替它完成第一条规则。",
                "因此若存在解，x 必须加入 B。",
                "一旦把 x 加入 B，就必须检查所有不超过 k 的 x 的倍数是否都在 A 中。",
                "检查通过后，这些倍数都已经被 x 覆盖，可以从未完成集合中删除。",
                "不断取最小未完成元素贪心，得到的 B 大小最小；若某次倍数缺失则无解。",
            ],
            "solution_brief": "关键观察：最小未覆盖元素没有更小因子可依赖，所以它被强制选入 B。用有序集合维护还没覆盖的 A 元素；每次取最小 x，检查 x,2x,3x...<=k 是否都出现，出现的从集合中删掉，失败输出 -1。",
            "primary_topic": "数论与同余",
        },
        "2160B": {
            "statement_brief": "给数组 b，其中 b_i 是所有以 i 结尾的子数组中不同元素个数之和。要求构造任意一个值域 1..n 的数组 a，使它能产生给定 b。",
            "transformed_statement": "把题目先看成：b_i-b_{i-1} 记录了 a_i 对多少个左端点产生了“新不同元素”的贡献，从而能定位 a_i 上一次出现的位置。",
            "key_observations": [
                "把 b_i-b_{i-1} 展开，每个左端点 l 只会贡献 0 或 1。",
                "若 a_i 没在子数组 a_l..a_{i-1} 中出现，f(l,i) 比 f(l,i-1) 多 1；否则不变。",
                "设 a_i 上一次出现位置为 x，则 l<=x 的子数组不会新增，l>x 的子数组都会新增。",
                "因此 b_i-b_{i-1}=x；若差值等于 i，说明 a_i 之前没出现过。",
                "所以差值小于 i 时令 a_i=a_x，差值等于 i 时随便放一个未用新值。",
            ],
            "solution_brief": "关键观察：差分 b_i-b_{i-1} 直接告诉你当前值上一次出现在哪里。顺序构造；记 d=b_i-b_{i-1}，若 d<i 则 a_i=a_d，否则给 a_i 一个新的未用编号。",
            "primary_topic": "构造与贪心",
        },
        "2146D1": {
            "statement_brief": "简单版给区间 [0,r]，两数组初始都为 0..r。可任意重排 a，最大化所有位置的 a_i OR b_i 之和，并输出一种重排。",
            "transformed_statement": "把题目先看成：a|b=(a+b)-(a&b)，所以只要能让每一对的按位与都为 0，就能达到显然上界。",
            "key_observations": [
                "所有 a 与 b 的总和固定，因此目标上界是两者总和，损失只来自 a_i&b_i。",
                "构造目标是让每个值 i 都配到一个与它按位无交集的值。",
                "取最小的 k 使 2^k>当前右端 r，则 mask=2^k-1 与区间内值互补。",
                "对后缀 [mask-r,r]，令 a_i=mask-i，可保证 a_i&i=0。",
                "删掉这段后，剩余前缀继续同样构造，直到全部配完。",
            ],
            "solution_brief": "关键观察：把最大 OR 变成消灭 AND。递归处理当前最大值 r：用全 1 掩码 mask=2^k-1 把后缀 [mask-r,r] 两两配成互补数，保证 AND 为 0；再缩小 r 处理剩余前缀。",
            "primary_topic": "构造与贪心",
        },
        "2140E1": {
            "statement_brief": "有 n 堆石子，每堆石子数在 1..m；若当前位置编号属于 good，就可以删除这一堆。Alice 和 Bob 轮流删到只剩一堆，Alice 最大化剩余石子数、Bob 最小化。简单版 m<=2，求所有配置的最终值总和。",
            "transformed_statement": "把题目先看成：m=2 时，每堆只需用一个二进制位表示它是 1 还是 2；对每个初始 mask 单独做删堆博弈 DP。",
            "key_observations": [
                "m=1 时所有配置最终值都是 1，答案直接为 1。",
                "m=2 时，最终值只可能是 1 或 2，可以把目标改成最终是否能留下值为 2 的堆。",
                "删除一堆后，后面的堆会重新编号，所以 DP 状态必须包含当前长度和当前 mask。",
                "Alice 的回合对所有可删位置取或，Bob 的回合对所有可删位置取与。",
                "枚举全部初始 mask，把 1+dp[n][mask][Alice] 加到答案中。",
            ],
            "solution_brief": "关键观察：简单版把石子数量压成二进制胜负。对每个 mask 做 dp[len][mask][player]，转移枚举当前 good 编号可删的堆并压缩 mask；Alice 取最大，Bob 取最小，最后累加所有 mask 的 1/2 结果。",
            "primary_topic": "动态规划与状态设计",
        },
        "2129B": {
            "statement_brief": "给排列 p。每个位置可保留 p_i，或改成 2n-p_i。要求最小化最终数组的逆序对数量。",
            "transformed_statement": "把题目先看成：对每个 p_i，它和所有比它小的元素不会形成逆序选择冲突；真正需要二选一的是比它大的元素在左边还是右边。",
            "key_observations": [
                "若选择 a_i=p_i，它作为较小值，只会与左侧所有比 p_i 大的元素形成逆序。",
                "若选择 a_i=2n-p_i，它变成很大的值，只会与右侧所有比 p_i 大的元素形成逆序。",
                "这两种代价只取决于 p_i 左右两边比它大的元素数量，与其他位置怎么选无关。",
                "因此每个位置可以独立取 min(左侧更大数数量, 右侧更大数数量)。",
                "题解也可从最小值开始递归删除：每删一个当前最小值，剩余问题结构完全相同。",
            ],
            "solution_brief": "关键观察：每个位置的选择代价独立。对每个 i 统计 leftGreater 和 rightGreater，答案累加 min(leftGreater,rightGreater)；n 总和较小，直接 O(n^2) 统计即可。",
            "primary_topic": "构造与贪心",
        },
        "2128B": {
            "statement_brief": "给排列 p，每次只能从双端取一个数形成 q。要求 q 中不存在连续 5 个严格递增或严格递减的子段，并输出取左/右方案。",
            "transformed_statement": "把题目先看成：比“避免 5 连单调”更强的是直接让 q 高低交替。",
            "key_observations": [
                "每一步可选的只有当前左端和右端两个数。",
                "奇数步取两端较小值，偶数步取两端较大值。",
                "若奇数步取到左端较小值，则右端较大值下一步仍在，所以下一步取到的值一定更大；右端对称同理。",
                "偶数步同理可证明下一步一定更小。",
                "所以 q_1<q_2>q_3<q_4...，自然不会出现长度 5 的严格单调段。",
            ],
            "solution_brief": "关键观察：构造一个更强的锯齿序列。第 1、3、5... 步取当前两端较小者，第 2、4、6... 步取较大者，并记录 L/R；锯齿性保证答案合法。",
            "primary_topic": "构造与贪心",
        },
        "2096G": {
            "statement_brief": "交互构造题：Alice 心里有 1..n 中的数。你必须一次性给出所有询问，每个询问把若干数分成左半、右半和不出现；Alice 会忽略恰好一个询问。要求用最少询问仍能确定数字。",
            "transformed_statement": "把题目先看成：每个数字对应一列三进制码，L/R/N 分别记成 -1/1/0；忽略一个询问就是缺失一位，需要用校验位恢复。",
            "key_observations": [
                "没有忽略时，q 次询问最多区分 3^q 个数，所以至少需要 ceil(log_3 n) 次。",
                "每一行询问要合法，等价于该行选出的 L 和 R 数量相等，也就是这一行的列值总和为 0。",
                "选择某列时同时选择它的相反列，可以保证每一行总和为 0；n 为奇数时再加入全 0 列。",
                "有一个回答被忽略时，需要任意缺失一位仍能还原原列；题解通过额外校验位让每列坐标和模 3 为 0。",
                "缺失位可由其余位的和唯一恢复，同时不同列不会只差一位。",
            ],
            "solution_brief": "关键观察：把询问表设计成带校验位的三进制编码。生成足够多的 {-1,0,1} 列，成对取列保证每个询问左右数量相等；再加一行校验，使每列和为 0 mod 3。交互返回中若一位缺失，用校验和补回后匹配唯一列。",
            "primary_topic": "交互",
        },
        "2077B": {
            "statement_brief": "交互题。有两个隐藏整数 x,y。最多询问两次形如 (n|x)+(n|y) 的值；之后给定 m，要求回答 (m|x)+(m|y)。",
            "transformed_statement": "把题目先看成：不需要恢复 x 和 y 本身，只要知道每个二进制位上 x,y 中有几个 1。",
            "key_observations": [
                "如果某一位在询问 n 中是 1，那么两个 OR 结果这一位都会被强制为 1，无法看出原始信息。",
                "所以用两个互补的交替 bitmask 分别让奇数位、偶数位暴露出来。",
                "先看两位小模型：根据查询和在该位附近的数值，可判断这一位上 x,y 是 00、01/10 还是 11。",
                "推广到所有位时，需要从低位到高位处理并扣掉已有进位。",
                "得到每一位的 1 的个数后，对任意 m：m 的该位为 1 则贡献 2 个 1，否则贡献隐藏的 1 的个数。",
            ],
            "solution_brief": "关键观察：两次询问交替遮住一半 bit，恢复的是每位 1 的数量。询问 0101... 和 1010...，按二进制从低到高结合进位解出每位 x,y 的 1 个数；读到 m 后逐位累加 OR 后的贡献。",
            "primary_topic": "交互",
        },
        "2040A": {
            "statement_brief": "先手从数组选一个下标 i，后手再选不同下标 j。若 |a_i-a_j| 不能被 k 整除则先手胜，否则后手胜；问先手能否保证胜并输出下标。",
            "transformed_statement": "把题目先看成：两个数差能被 k 整除，当且仅当它们模 k 的余数相同。",
            "key_observations": [
                "若先手选的数所在余数类还有其他数，后手就选同余数的那个数，差值被 k 整除，先手输。",
                "若先手选的数是其余数类中唯一元素，后手无论选哪个不同下标，余数都不同。",
                "余数不同意味着差值不被 k 整除，先手必胜。",
                "因此可赢下标等价于余数类大小为 1 的下标。",
            ],
            "solution_brief": "关键观察：游戏完全由 mod k 分组决定。统计每个 a_i mod k 的出现次数；存在出现一次的余数类就输出对应下标，否则输出 NO。",
            "primary_topic": "博弈",
        },
        "2029H": {
            "statement_brief": "无向图每条边每天独立按概率出现。初始只有 1 号点有消息；每天结束时，点若自身已有消息或与前一天有消息的点通过当天出现的边相邻，则获得消息。求所有点获得消息所需天数的期望。",
            "transformed_statement": "把题目先看成：消息集合只会单调扩大，所以状态是已获知点集 S；困难在于高效算从 S 扩到新集合的概率和停留期望。",
            "key_observations": [
                "设 dp_S 为恰好到达集合 S 的概率，答案可写成 sum dp_S*tr_S。",
                "tr_S 是从 S 等到至少一个外部点被感染的期望时间；每天无扩张概率是所有跨割边都不出现的乘积。",
                "直接枚举从 S 扩到 S∪T 的 T 会得到 3^n 级别转移。",
                "题解把“真实新增集合落在某个范围内”的概率写成若干集合函数乘积，再用容斥得到精确新增集合概率。",
                "这些系数可整理成 Const*f_{S∪T}*g_S*h_T 的形式，从而用子集卷积优化到 O(2^n*n^2)。",
            ],
            "solution_brief": "关键观察：先把期望改成状态概率乘几何等待时间，再用容斥优化转移。维护只包含 1 的子集 DP；对每个 S 计算停留期望 tr_S，并通过子集卷积批量求出扩张到各个 S∪T 的概率，最后累加 dp_S*tr_S。",
            "primary_topic": "组合计数与概率",
        },
        "2255E2": {
            "statement_brief": "困难版数组初值和赋值可以是任意整数，支持区间赋值、取负、截成 max(a_i,0) 和历史点查询；查询仍要求某位置所有历史值序列的最大非空子数组和。",
            "transformed_statement": "把题目先看成：简单版的历史最大子段框架不变，难点是把任意初值下的操作段仍压成常数大小懒标记。",
            "key_observations": [
                "第一次赋值之前，固定初值符号后，值只可能是 -|x|、0、|x|，可以用系数序列摘要表示历史。",
                "第一次赋值之后，后续历史与原始 x 无关，变成普通固定数值序列摘要。",
                "因此一个操作段可拆成“依赖 |x| 的系数前缀”和“赋值后的固定数值后缀”，并且拼接时仍能 O(1) 合并。",
                "另一种做法是把 max(a,0) 直接在线段树上物化：若整段非负则不动，整段非正则赋 0，正负混合才递归。",
                "用正负混合节点数量作势能，可证明所有截断递归总成本是摊还 O(n+q log n)。",
            ],
            "solution_brief": "关键观察：历史查询仍用四元组最大子段摘要；困难版只修懒标记。可用“系数前缀 + 固定后缀”表示任意操作段并常数合并，或用 min/max 势能把截断操作物化为赋 0；点查询和记录版本顺序沿用 简单版。",
            "primary_topic": "数据结构",
        },
        "2252B": {
            "statement_brief": "给二进制串，允许删除字符使剩余串交替；但删除序列本身也必须 0/1 严格交替。求最少删除次数，无法做到输出 -1。",
            "transformed_statement": "把题目先看成：最终保留串交替，删除串也要交替；两者都只关心 0 和 1 的数量差是否能落在 {-1,0,1} 附近。",
            "key_observations": [
                "删除串严格交替，意味着删除的 0 数和 1 数之差绝对值最多为 1。",
                "设原串 0/1 数量差为 Δn，最终串数量差为 Δk，则必须满足 |Δn-Δk|<=1。",
                "交替串的 Δk 只能是 -1、0 或 1，所以若 |Δn|>2 直接无解。",
                "为了少删字符，先贪心压缩原串：每段连续相同字符只保留一个，得到最长交替子序列长度 L。",
                "若压缩串的数量差 ΔL 不在允许区间 [Δn-1,Δn+1]，只需从两端继续删掉若干字符把差值调进去。",
            ],
            "solution_brief": "关键观察：先保留最长交替骨架，再用数量差修正删除序列合法性。若 |Δn|>2 输出 -1；否则压缩相邻重复得到 L 和 ΔL，答案为 (n-L)+max(0, |Δn-ΔL|-1)。",
            "primary_topic": "字符串",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2234B": {
            "statement_brief": "给定 n，要求找两个正整数 a,b，使 a+b=n，a 是十进制回文数，b 能被 12 整除；不存在则输出 -1。",
            "transformed_statement": "把题目先看成：只要找一个回文数 a，使 a 与 n 在模 12 下同余，剩下的 b=n-a 就一定合法。",
            "key_observations": [
                "除余数 10 外，0..11 中每个模 12 余数本身都可以由一个很小的回文数表示。",
                "余数为 10 时，22 是回文且 22 mod 12 = 10。",
                "所以 n mod 12 != 10 时取 a=n mod 12，余数为 10 时取 a=22。",
                "唯一需要单独排除的是 n=10，此时 a 不能取 22，其他正回文也无法让 b 为 12 的倍数。",
            ],
            "solution_brief": "关键观察：构造 a 只需要匹配 n 的模 12 余数。若 n=10 输出 -1；否则当 n mod 12=10 时取 a=22，其他情况取 a=n mod 12，再令 b=n-a 输出。",
            "primary_topic": "构造与贪心",
        },
        "2229B": {
            "statement_brief": "给两个长度为 n 的数组 a,b，每个位置可以交换 a_i 和 b_i，要求最大化 max(a)+sum(b)。",
            "transformed_statement": "把题目先看成：除了承担最终 max(a) 的位置外，每一对数都更希望把较大的数放进 b 的求和里。",
            "key_observations": [
                "若一个位置不负责最终的 max(a)，它只通过 b_i 贡献答案，较大值放在 b_i 不会更差。",
                "每个位置先贡献 max(a_i,b_i) 到 sum(b) 是自然上界的一部分。",
                "最终还需要有一个位置提供 max(a)，这个位置能额外贡献它那一对中的较小值。",
                "因此只需在所有较小值里再取最大者作为 max(a) 的来源。",
            ],
            "solution_brief": "关键观察：每对数的较大值都应进入 b 的总和，唯一例外是还要从某一对拿较小值去做 max(a)。答案为 sum(max(a_i,b_i))+max(min(a_i,b_i))。",
            "primary_topic": "构造与贪心",
        },
        "2222G": {
            "statement_brief": "给一棵 n 点树。对每个点对 (u,v)，删除 u 到 v 路径上的所有边后，记最大连通块大小为该点对的值；要求统计每个可能值出现的点对数。",
            "transformed_statement": "把题目先看成：按路径的 LCA/最高点 o 分治统计，路径两端落在 o 的不同子树时，答案可以写成几个与端点相关的最大值。",
            "key_observations": [
                "以重心作为当前分治根 o，可以保证递归子问题规模受控。",
                "对 LCA 为 o 的路径，设 a_x 为删掉 x-o 路径后非 o 侧最大块，b_x 为删掉 o 后 x 所在子树大小，则值是 max(a_x,a_y,n-b_x-b_y)。",
                "若最大值来自 a_x 或 a_y，至少有一端所在子树规模达到 n/3，因此真正需要特殊处理的大子树很少。",
                "若最大值来自 n-b_x-b_y，则问题变成按 b 值组合计数，可用 heavy/light、差分和卷积式合并压复杂度。",
            ],
            "solution_brief": "关键观察：把路径删除后的最大块拆成 a_x、a_y、n-b_x-b_y 三类来源。对每个重心 o 统计跨子树点对；大子树只会有常数个，其他子树按大小桶合并，用二分/差分处理前两类，用 heavy-light 式合并处理第三类，总体 O(n log n)。",
            "primary_topic": "树结构",
        },
        "2222E": {
            "statement_brief": "交互题。隐藏 k in {1,2,3} 和 c，函数分别是 x&c、x|c、x xor c；允许插入 f(x) 或查询集合中大于等于 y 的个数，要求在 n+3 次内确定 k,c。",
            "transformed_statement": "把题目先看成：集合里插入 f(0) 和 f(2^n-1) 后，三种位运算在极值输入上的行为几乎完全不同。",
            "key_observations": [
                "先把 0 放进集合，再插入 f(0)：若集合大小没变，则 f(0)=0，只可能是 AND 情况。",
                "AND 情况下再查询/二分 f(2^n-1)，即可得到 c。",
                "若插入 f(0) 后集合大小变大，则 k 是 OR 或 XOR，并且 f(0)=c。",
                "再插入 f(2^n-1)：OR 会得到全 1，XOR 会得到 c 的按位补；除 c=全 1 的边界外可直接区分。",
                "当 c=全 1 时，改查 f(1) 是否仍为全 1 来区分 OR 和 XOR。",
            ],
            "solution_brief": "关键观察：用 0 和全 1 两个极端输入做指纹。先插入 f(0) 判断 AND 或 OR/XOR，并用查询定位 c；随后用 f(2^n-1) 区分 OR 与 XOR，c=全 1 时再补一次 f(1) 判边界。",
            "primary_topic": "交互",
        },
        "2191A": {
            "statement_brief": "给一个排列，要求给每张卡染两种颜色，使原顺序相邻卡异色，按数值排序后的相邻卡也异色；判断是否可行。",
            "transformed_statement": "把题目先看成：原顺序相邻异色已经强制颜色按位置奇偶交替，剩下只需检查数值排序后的奇偶是否也交替。",
            "key_observations": [
                "只考虑原数组相邻异色时，合法染色只有两种：奇偶位置互换颜色。",
                "按值排序后，第 1,2,3... 小的元素也必须颜色交替。",
                "因此每个值 a_i 的排名就是 a_i，它的颜色必须与位置 i 的奇偶关系整体一致或整体相反。",
                "等价于所有 a_i 与 i 的奇偶性差异数量只能是 0 或 n。",
            ],
            "solution_brief": "关键观察：两套相邻异色都在要求一个交替序列。统计满足 a_i%2 != i%2 的位置数 cnt；若 cnt 为 0 或 n，则两种交替染色之一可行，否则不可行。",
            "primary_topic": "构造与贪心",
        },
        "2190G": {
            "statement_brief": "给 n*n 的 0/1 区间矩阵，每行的 1 是一个连续区间；每行可付费改成另一个区间。求把矩阵行列式变成最大可能值时的最小总代价。",
            "transformed_statement": "把题目先看成：区间行做差分后变成连接 l_i 与 r_i+1 的一条边，行列式非零性转化为这 n 条边在 n+1 个点上的无环结构。",
            "key_observations": [
                "区间矩阵的行列式只可能是 -1、0、1，因此最大目标值是 1。",
                "对每行做差分并补一列后，区间 [l,r] 变成端点 l 和 r+1 上的边。",
                "矩阵非零等价于这些边在 n+1 个点上构成无环图；n 条边要达到满秩时对应一棵树。",
                "当已经是树时，行列式符号由边方向翻转数和边编号诱导排列的奇偶决定。",
                "当 det 为 -1 或 0 时，修改问题变成用最小代价换边，让图成为符号正确的树。",
            ],
            "solution_brief": "关键观察：先把代数问题变成图上的换边问题。差分后每一行是一条边，det 非零对应成树，det 符号由方向和排列奇偶确定；若当前 det=-1，尝试单行或两行修改翻符号，若 det=0，则按连通分量/唯一环情况做最小代价补边或换边。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2189A": {
            "statement_brief": "给 h,l 和数组，选择偶数个数并配成有序对 (x,y)。若 1<=x<=h 且 1<=y<=l，则该对能给表格中的一个合法格子贡献 1；求最大贡献。",
            "transformed_statement": "把题目先看成：每个有效 pair 至少需要一个不超过 h 的数，并且两个数都必须不超过 l。",
            "key_observations": [
                "可先交换 h,l，使 h<=l，不影响最大贡献。",
                "每个合法 pair 都消耗一个 <=h 的数，所以答案不超过 cnt_h。",
                "每个合法 pair 还消耗两个 <=l 的数，所以答案不超过 floor(cnt_l/2)。",
                "题解分情况证明这个上界可达：小数足够时两两配，大数不足时让每对都含一个 <=h 的数。",
            ],
            "solution_brief": "关键观察：答案就是两个必要条件的较小者。统计 cnt_h=#{a_i<=h} 和 cnt_l=#{a_i<=l}，输出 min(cnt_h, cnt_l//2)。",
            "primary_topic": "构造与贪心",
        },
        "2183A": {
            "statement_brief": "Alice 和 Bob 在二进制数组上轮流操作：每次选长度至少 2 的子数组，把它替换成 1-min(subarray)。最后剩一个数时，Alice 希望它为 0，Bob 希望它为 1；判断胜者。",
            "transformed_statement": "把题目先看成：最后一次合并必然会涉及某个原数组端点，所以胜负只由两端是否存在 1 决定。",
            "key_observations": [
                "若数组全为 1，Alice 直接选整个数组，会得到 0 并获胜。",
                "若左端是 1，Alice 可以先合并 [2,n]；这段含 0 时会变成 1，留给 Bob 的是两个 1，Bob 只能合成 0。",
                "右端是 1 时完全对称，Alice 也能把局面交给 Bob 处理两个 1。",
                "若两端都是 0，Alice 不能一次吃掉两端，否则整段变 1 立即不利；无论她怎么操作，Bob 都能在之后合并含 0 的整段得到 1。",
            ],
            "solution_brief": "关键观察：中间结构不重要，两端控制最后一合并。若 a_1 或 a_n 为 1，输出 Alice；否则输出 Bob。",
            "primary_topic": "博弈",
        },
        "2180G": {
            "statement_brief": "维护一个动态数组：操作 1 删除中间元素，操作 2 在开头、结尾和每两个元素之间插入 x，操作 3 查询所有非空子序列 balance 的总和。",
            "transformed_statement": "把题目先看成：数组在所有操作后始终保持回文，所有子序列的复杂位置权重可以被对称性化简成只依赖长度 n 和元素和 S 的公式。",
            "key_observations": [
                "操作 2 会在所有间隙插入同一个 x，操作 1 删除中点，因此回文性始终保持。",
                "把一个元素和它的镜像位置配对后，子序列 balance 中的位置权重会成对抵消大量细节。",
                "化简后查询答案只依赖当前长度 n 与元素和 S，而不需要知道完整数组。",
                "题解得到的形式是 S/2 * (2^(n-1) + (2^n-1)/n)，可预处理幂和逆元。",
                "唯一还要支持的是删除中点；对每个插入值维护状态并从最近插入值倒跳，可摊还 O(1) 找到当前中点。",
            ],
            "solution_brief": "关键观察：回文对称把全体子序列的 balance 总和压成长度与元素和的函数。维护 n 和 S；插入 x 时 n=2n+1、S=S+(旧 n+1)x，删除时找到并扣掉当前中点，查询直接套公式。",
            "primary_topic": "组合计数与概率",
        },
        "2174F": {
            "statement_brief": "给每个点的颜色，并给每种颜色要求其总度数奇偶性。要求计数满足这些奇偶要求的标号树数量。",
            "transformed_statement": "把题目先看成：标号树可由 Prüfer 序列表示，颜色总度奇偶性等于颜色点数加上该颜色在 Prüfer 序列中的出现次数。",
            "key_observations": [
                "在 Prüfer 序列中，顶点度数等于出现次数加 1。",
                "因此颜色 c 的总度奇偶只取决于 count_c 与该颜色在序列中的出现次数奇偶。",
                "用加减号角色滤波可以把奇偶约束写成对所有符号选择的求和。",
                "固定符号后，所有 Prüfer 序列的贡献只剩 (sum eps_c*count_c)^(n-2)。",
                "按负号颜色的点数总和 k 分组，用多项式乘法求每个 k 的系数，再累加 (n-2k)^(n-2)。",
            ],
            "solution_brief": "关键观察：Prüfer 序列把树度数限制变成颜色出现次数的奇偶限制。用 ±1 滤波消掉奇偶条件，再把同类项按负号颜色总点数 k 聚合，构造多项式求系数，最终累加 A_k*(n-2k)^(n-2) 并乘上 2^{-m}。",
            "primary_topic": "组合计数与概率",
        },
        "2161A": {
            "statement_brief": "给初始 rating、Div.2 门槛 X、单场最大可控变化 D 和赛程字符串 1/2；Div.1 总是 rated，Div.2 只有 rating<X 才 rated，求最多能参加多少场 rated round。",
            "transformed_statement": "把题目先看成：一旦 rating 降到 X-1，以后的 Div.2 也都会 rated，因此目标是在尽量早的时候把 rating 压到门槛下。",
            "key_observations": [
                "Div.1 场永远 rated，所以它既贡献答案，也可以用来主动降 rating。",
                "当前 rating<X 时，之后所有 Div.1 和 Div.2 都会 rated，直接全计入。",
                "当前 rating>=X 时，Div.2 不 rated，只有遇到 Div.1 才能继续降分。",
                "每次可控变化最多 D，最优策略是在每场 rated 后尽量把 rating 降到 X-1。",
            ],
            "solution_brief": "关键观察：不要保存 rating，能降就尽早降。顺序模拟赛程；Div.1 总计入并把 rating 减 D，若降到 X 以下则后续全计入；Div.2 只有当前 rating<X 时计入。",
            "primary_topic": "构造与贪心",
        },
        "2159F": {
            "statement_brief": "交互题。n*n 网格是 1..n^2 的排列，存在长度 1..n 的隐藏蛇路径；可询问 f(l,T)，即长度 l 的蛇在时刻 T 覆盖的最大格值，要求找出 m 个最小的 f(l,T)。",
            "transformed_statement": "把题目先看成：固定蛇长 l 后，时间轴可切成若干段，每段上的 f(l,T) 呈单峰结构，然后从所有单调/单峰段中归并取最小值。",
            "key_observations": [
                "固定 l 和一个长度 l 的时间窗口，若 f(l,T) 上升，说明新蛇头成为当前最大值。",
                "这个最大值至少还会在蛇身中停留 l 秒，因此窗口内函数不会任意震荡。",
                "于是每个长度 l 的时间块可视作单峰段，可以用三分式查询找极小区域。",
                "遇到相等平台时还需要额外判断方向，才能把段拆成可归并的单调片段。",
                "所有蛇长的段数总量约为 sum n/l = O(n log n)，最后用优先队列合并取前 m 小。",
            ],
            "solution_brief": "关键观察：固定长度后的时间序列有单峰性。对每个 l 把时间轴分段，在每段上用三分和平台方向判定找出单调片段，再把这些片段丢进优先队列，像多路归并一样取全局最小的 m 个查询值。",
            "primary_topic": "交互",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2143C": {
            "statement_brief": "给一棵带权树，每条边 (u,v) 有两个收益 x,y。要给每个点分配 1..n 的一个排列值；若边两端满足指定大小关系取 x，否则取 y。要求构造一个让总收益最大的排列。",
            "transformed_statement": "把题目先看成：每条边都想独立拿到 max(x,y)，于是把“谁的排列值更小”转成一条有向约束边。",
            "key_observations": [
                "若一条边取 y 更优，就要求 p_u<p_v；若取 x 更优，就要求 p_u>p_v。",
                "把每条边按更优方向定向后，因为原图是一棵树，得到的有向图不可能出现有向环。",
                "有向无环图可以拓扑排序，拓扑序中靠前的点赋更小排列值即可满足所有定向约束。",
                "因此每条边都能同时拿到自己的较大收益，总和达到显然上界。",
            ],
            "solution_brief": "关键观察：树上任意边定向后仍是 DAG。对每条边，若 y>=x 就定向 u->v，否则定向 v->u；拓扑排序后按顺序赋值 1..n，所有边都得到 max(x,y)。",
            "primary_topic": "构造与贪心",
        },
        "2124B": {
            "statement_brief": "给数组 a，最多一次选择 i<j，把 a_j 加到 a_i 上并把 a_j 置 0；要求最小化所有前缀最小值之和。",
            "transformed_statement": "把题目先看成：只要能在很靠前的位置制造 0，后面所有前缀最小值都会变成 0。",
            "key_observations": [
                "前两个前缀的贡献无法同时消掉，答案至少受 a_1 和 min(a_1,a_2) 控制。",
                "若 a_1>a_2，可以用 i=1,j=2，使第二项变 0，前缀和只剩 a_1+a_2。",
                "若 a_1<=a_2 且 n>=3，可以用 i=2,j=3，使第三项起前缀最小值为 0，前两项贡献为 a_1+a_1。",
                "n=2 时不能使用 j=3，但不操作也正好得到 a_1+min(a_1,a_2)。",
            ],
            "solution_brief": "关键观察：最优值只由前两项决定。直接输出 min(2*a_1, a_1+a_2)；第一个分支对应保持前两项都被 a_1 控制，第二个分支对应把第二个前缀之后尽早压成 0。",
            "primary_topic": "构造与贪心",
        },
        "2120D": {
            "statement_brief": "给 a,b,k，要求找字典序最小的矩阵尺寸 (n,m)，使任意 n*m、元素在 1..k 的矩阵中，必然存在一个 a 行 b 列且所有元素相同的子矩阵。",
            "transformed_statement": "把题目先看成：先让每一列必然有 a 个相同值，再把“这一列选出的值和行集合”当作抽屉继续逼出 b 列相同。",
            "key_observations": [
                "为了让一列中必有 a 个相同元素，最小行数是 n=k(a-1)+1。",
                "固定一列后，可记录一个元组：相同值 v，以及它出现的 a 个行位置。",
                "这样的元组最多有 k*C(n,a) 种。",
                "若列数 m=(b-1)*k*C(n,a)+1，则由抽屉原理必有 b 列拥有同一个元组。",
                "这些列在同一组 a 行上取同一个值，于是形成目标 a*b 全等子矩阵。",
            ],
            "solution_brief": "关键观察：连续用两次抽屉原理。先取 n=k(a-1)+1；再令 m=(b-1)*k*C(n,a)+1。组合数按模数计算，输出 n,m 的模值。",
            "primary_topic": "组合计数与概率",
        },
        "2119C": {
            "statement_brief": "给 n,l,r,k，要求构造字典序最小的长度 n 数组，所有数在 [l,r]，且全体按位 AND 等于全体 XOR；只需输出第 k 项。",
            "transformed_statement": "把题目先看成：奇数个相同的 l 已经满足条件；偶数个数时，需要让最后两个数相等且与 l 按位没有交集。",
            "key_observations": [
                "n 为奇数时，数组全填 l，则 AND 和 XOR 都等于 l。",
                "n=2 时两个正数若满足 AND=XOR 基本只能退化到 0，不符合 l>=1，因此无解。",
                "n 为偶数且大于 2 时，为了字典序最小，前 n-2 项应尽量保持为 l。",
                "剩下两个数若都为 z，则它们的 XOR 抵消为 0；同时要让整体 AND 为 0，需要 l&z=0。",
                "满足 z>=l 且 l&z=0 的最小 z 是严格大于 l 的最小 2 的幂；若它超过 r 则无解。",
            ],
            "solution_brief": "关键观察：偶数情况只改最后两位。若 n 为奇数输出 l；若 n=2 输出 -1；否则取 p 为大于 l 的最小 2 的幂，若 p>r 输出 -1，若 k<=n-2 输出 l，否则输出 p。",
            "primary_topic": "构造与贪心",
        },
        "2110A": {
            "statement_brief": "给数组，每次可删除任意一个元素，要求让剩余数组的最小值与最大值之和为偶数，求最少删除次数。",
            "transformed_statement": "把题目先看成：排序后，删除只是在左右两端缩短区间；合法条件等价于当前左右端点奇偶性相同。",
            "key_observations": [
                "排序后，剩余数组的最小值是当前最左未删元素，最大值是当前最右未删元素。",
                "若初始两端奇偶相同，答案为 0。",
                "若两端奇偶不同，只需要改变其中一端的奇偶性。",
                "删除左侧元素直到遇到第一个与原最小值奇偶不同的数，或删除右侧元素直到遇到第一个与原最大值奇偶不同的数，取较少者。",
            ],
            "solution_brief": "关键观察：只看排序后两端。排序 a；若 a_1 与 a_n 同奇偶输出 0，否则分别计算从左删到奇偶改变、从右删到奇偶改变的代价，输出较小值。",
            "primary_topic": "构造与贪心",
        },
        "2067A": {
            "statement_brief": "给两个数 x,y，判断是否存在整数 n，使十进制数位和 S(n)=x 且 S(n+1)=y。",
            "transformed_statement": "把题目先看成：n 加一时，若末尾有 k 个 9，这些 9 会变成 0，前一位加 1。",
            "key_observations": [
                "若 n 末尾没有 9，则 S(n+1)=S(n)+1。",
                "若 n 末尾有 k 个连续的 9，则加一会先增加 1，再损失 9k 的数位和。",
                "因此必须有 y=x+1-9k，其中 k 是非负整数。",
                "反过来，只要 (x+1-y) 是非负的 9 的倍数，就能构造出满足条件的 n。",
            ],
            "solution_brief": "关键观察：数位和变化只取决于末尾连续 9 的个数。判断 d=x+1-y；若 d>=0 且 d%9==0 输出 YES，否则输出 NO。",
            "primary_topic": "数论与同余",
        },
        "2066B": {
            "statement_brief": "给非负整数序列，要求选最长子序列，使任意切分点都满足左侧前缀最小值不小于右侧后缀 mex。",
            "transformed_statement": "把题目先看成：0 的数量决定上界；没有 0 的序列一定合法，而含两个 0 的序列一定不合法。",
            "key_observations": [
                "若一个序列没有 0，则任意后缀 mex 都是 0，条件必然成立。",
                "若一个序列含至少两个 0，取刚包含第一个 0 但还没包含第二个 0 的前缀，左侧最小值为 0，右侧 mex 大于 0，条件失败。",
                "所以答案只可能是非零元素个数，或非零元素个数加 1。",
                "若想多保留一个 0，最优是保留原序列中最左边的 0，再带上所有非零元素。",
                "只需对这个候选子序列检查一次 magical 条件即可决定能否加 1。",
            ],
            "solution_brief": "关键观察：最多只能保留一个 0。若没有 0，答案 n；否则先取所有非零元素得下界 n-cnt0，再尝试加入最左 0，线性计算前缀最小和后缀 mex 检查是否合法，合法则答案加 1。",
            "primary_topic": "构造与贪心",
        },
        "2048A": {
            "statement_brief": "给一个整数 x。每次可以从十进制表示中删除一段相邻的数字 33，或在 x>=33 时把 x 减去 33；判断能否把 x 变成 0。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是一个关于十进制删除相邻 33 与整体减 33 两种操作的可达性判定题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "基础实现与模拟",
        },
        "2021A": {
            "statement_brief": "给数组，每次选择两个数删掉并把它们向下取整的平均值加入数组；不断操作到只剩一个数，求最后数值的最大可能值。",
            "transformed_statement": "把题目先看成：每个初始数对最终答案有一个系数，总系数固定为 1；大的数应该尽量晚参与合并，拿到更大的系数。",
            "key_observations": [
                "暂时忽略 floor 时，最终值是所有初始数的加权平均，权重和固定。",
                "一个数越晚参与合并，它被除以 2 的次数越少，最终系数越大。",
                "因此应让小数先互相合并，把大数留到后面。",
                "题解指出这个顺序在带 floor 的原问题中仍然最优。",
            ],
            "solution_brief": "关键观察：排序后从小到大滚动合并即可。先升序排序，令 cur=a_1；依次执行 cur=(cur+a_i)//2，最后的 cur 就是最大可达值。",
            "primary_topic": "构造与贪心",
        },
        "2013C": {
            "statement_brief": "交互题。隐藏一个长度为 n 的二进制串，每次可询问一个二进制串是否为其子串，要求在 2n 次询问内确定原串。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：核心任务是用子串存在性询问逐步还原隐藏二进制串。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2246B": {
            "statement_brief": "给 n，要求构造 n 个互不相同的正整数，使总和能被每一个元素整除；无解则输出 -1。",
            "transformed_statement": "把题目先看成：若已有一组数都整除当前总和 S，那么追加 S 后，新总和变成 2S，旧数和新数都仍能整除总和。",
            "key_observations": [
                "n=2 无解：若 x,y 都整除 x+y，则 lcm(x,y) 也整除 x+y；但 x!=y 时 lcm(x,y) 至少超过 x+y 的可承受范围，矛盾。",
                "n=1 可以取 [1]，n=3 可以取 [1,2,3]。",
                "对 n>3，从 n-1 的构造出发，设旧总和为 S，追加新元素 S。",
                "旧元素都整除 S，因此也整除 2S；新元素 S 也整除 2S。",
                "每次追加都会让总和翻倍，n<=50 时数值仍在 10^17 限制内。",
            ],
            "solution_brief": "关键观察：用“追加旧总和”递推构造。n=2 输出 -1；n=1 输出 1；n=3 输出 1 2 3；更大 n 从 [1,2,3] 开始反复追加当前总和即可。",
            "primary_topic": "数论与同余",
        },
        "2237A": {
            "statement_brief": "一排塔依次执行一次操作：选择塔 i 后，它会把右边第一个比它高的塔削到与自己同高。可任意安排操作顺序，求最终塔高总和最小值。",
            "transformed_statement": "把题目先看成：从左到右操作时，低塔会逐个把右侧第一个仍更高的塔压下来，最终每个位置都会变成它左侧前缀最小值。",
            "key_observations": [
                "从左到右操作是最优顺序。",
                "处理到第 i 个塔时，它的高度已经不会低于前缀最小值，也能把右侧第一个更高塔压到当前高度。",
                "这个过程会把后续高塔逐步传递压低。",
                "最终第 i 个位置的高度正好是 min(a_1,...,a_i)。",
            ],
            "solution_brief": "关键观察：最小最终数组就是前缀最小值数组。顺序扫描维护 mn=min(mn,a_i)，把 mn 累加到答案即可。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2228A": {
            "statement_brief": "给一串只含 0、1、2 的数。每次选一个非空子序列，只要其元素和是 3 的倍数，就把它们全部删除；求最多能进行多少次删除。",
            "transformed_statement": "把题目先看成：0 可以单独拿走，1 和 2 尽量配成和为 3 的二元组，剩余同类元素再每三个组成一组。",
            "key_observations": [
                "把一个含 0 的组拆出单独的 0 不会降低操作次数，因此所有 0 都应各自作为一次操作。",
                "含有 1 和 2 的组可以拆成一个 [1,2] 或 [2,1]，剩余部分仍可独立处理；所以先贪心配掉异类对。",
                "配对后剩下的元素只有单一值，能进行的操作就是每三个 1 或每三个 2 一组。",
            ],
            "solution_brief": "关键观察：最优操作可规范化为单个 0、一个 1/2 配对、以及三个同值元素三种形式。统计 0 的个数，加上 min(cnt1,cnt2) 个异类对，再加上剩余 1 和 2 各自除以 3 的商。",
            "primary_topic": "构造与贪心",
        },
        "2211C2": {
            "statement_brief": "给数组 a、含有 -1 的数组 b 和窗口长度 k。要求把 b 中的 -1 替换成 1..n 的数，使 a 与 b 的每个长度 k 子数组都是同一个多重集合。",
            "transformed_statement": "把题目先看成：窗口右移一格只会从多重集合中删去 a_l、加入 a_r，因此沿着同一余数类的下标链，变化必须由端点值完全解释。",
            "key_observations": [
                "从窗口 [l,r] 移到 [l+1,r+1] 时，a 侧丢掉 a_l、得到 a_r；b 侧必须实现同样的多重集合变化。",
                "若一条下标链上的 a 值不全相同，内部位置不能被任意改写，必须满足 b_i=a_i（已知值不一致立即失败）。",
                "若一条链上的 a 值全相同，则 b 中的非 -1 值只能全部相同；它相当于从 a 的前 k 个位置借用一个同值链。",
                "最后只需检查前 k 个位置提供的每种值数量是否足够覆盖这些全相同链的需求，剩余 -1 可以补齐。",
            ],
            "solution_brief": "关键观察：按下标模 k 分成 k 条链；每条链要么 a 全相同并允许 b 整链取这个值，要么 b 的每个已知位置都被 a 强制固定。扫描每条链检查一致性，再用前 k 个 a 的频次核对可借出的同值链数量。",
            "primary_topic": "字符串",
        },
        "2176C": {
            "statement_brief": "有若干硬币，按顺序恰好取 k 枚放入袋中；袋中总和一旦变成偶数就会立刻被清空。对每个 k，求最后袋中分数的最大值。",
            "transformed_statement": "把题目先看成：袋子非空时必须保持奇数和，所以最后留下的部分只能由奇数硬币开头，再接若干偶数硬币；多余奇数只能成对放入并触发清空。",
            "key_observations": [
                "若所有硬币都是偶数，第一次放入就清空，所有答案都是 0。",
                "若最终袋中有分数，袋中必须含奇数个奇数硬币；为了最大化，应保留最大的奇数，并选最大的若干偶数。",
                "先用一个奇数加降序偶数可以覆盖前 m+1 个 k；更大的 k 通过在开头加入两个额外奇数让袋子清空，再重新积累偶数，能按奇数个数继续扩展。",
                "当选取的奇数总数为偶数时，最后一定清空，因此相应答案为 0。",
            ],
            "solution_brief": "关键观察：只需按奇偶数量构造。排序偶数并做前缀和；逐步增加选取数量，优先加入偶数，偶数用完后每增加两个奇数就重置一次袋子，若当前袋中奇数数为奇数则答案为最大奇数加所选偶数和，否则为 0。",
            "primary_topic": "构造与贪心",
        },
        "2163B": {
            "statement_brief": "给一个排列 p 和目标二进制串 x。一次操作选择区间 [l,r]，把区间内部且数值严格位于 p_l、p_r 之间的位置标成 1；最多操作 5 次，要求覆盖 x 中所有的 1。",
            "transformed_statement": "把题目先看成：端点位置和端点数值都不能被这种操作覆盖，先找出数值最小点与最大点，再用它们把排列位置划成三段。",
            "key_observations": [
                "位置 1、n 永远不是区间内部，数值 1、n 所在位置也不可能作为严格内部点，因此这四个位置上的目标位必须都是 0。",
                "设 pos_1、pos_n 是最小值和最大值的位置；若这两个位置上的目标位为 0，就可以用它们和数组两端作为端点覆盖所有其它位置。",
                "操作 [1,pos_1]、[1,pos_n] 覆盖左段，操作 [pos_1,n]、[pos_n,n] 覆盖右段，操作 [min(pos_1,pos_n),max(pos_1,pos_n)] 覆盖中段。",
            ],
            "solution_brief": "关键观察：不可覆盖的位置恰好包括两端和最小/最大值位置。若这些位置没有被要求置 1，至多五个固定区间就能覆盖三段中的所有位置；否则无解。",
            "primary_topic": "构造与贪心",
        },
        "2134F": {
            "statement_brief": "给出 0、1、2、3 的出现次数，统计所有不同排列中相邻 XOR 的最低位值之和（oddness）分别等于每个 k 的排列数量。",
            "transformed_statement": "把题目先看成：按数值奇偶把排列切成红蓝段；跨红蓝段的相邻对贡献固定为 1，段内贡献只由同奇偶组内部 0/2 或 1/3 的切换次数决定。",
            "key_observations": [
                "0 与 2 的最低位相同，1 与 3 的最低位相同；红蓝相邻时 XOR 的最低位为 1，红红或蓝蓝相邻时贡献为 0 或 2。",
                "因此先枚举红段数、蓝段数，再分别统计每种颜色内部被切成若干段时产生的偶数贡献，最后做卷积合并。",
                "一个由两种符号组成且总数固定的字符串可按 run 数枚举；run 长度分配用组合数，切段位置再按不同/相同邻接分别选择。",
                "段数相差至多 1，红蓝段之间的边贡献由段数直接决定，避免枚举完整排列。",
            ],
            "solution_brief": "关键观察：将排列分解为交替的红蓝段，外层枚举两色段数并卷积 oddness；每种颜色的内部表通过枚举 run 数、用组合数分配 run 长度和切分位置得到，整体复杂度为 O(n^3)。",
            "primary_topic": "组合计数与概率",
        },
        "2118B": {
            "statement_brief": "初始矩阵每一行都是 1..n。每次可以反转某一行的一个子数组，要求至多 2n 次操作后每一列都成为一个排列。",
            "transformed_statement": "把题目先看成：目标矩阵取单位排列的所有循环移位；关键是用三次区间反转模拟一次循环移位，并利用第一步在每行相同而抵消。",
            "key_observations": [
                "让第 i 行成为单位排列的一个不同循环移位后，每列恰好包含 1..n。",
                "数组循环移位可以由三次反转完成：反转 [1,n]、[1,i]、[i+1,n]（等价的移位方向按实现约定选择）。",
                "所有行的 [1,n] 反转可以省略或统一处理，因为它对构造只贡献一个公共初始变换，最终只需为每行输出两次有效反转。",
            ],
            "solution_brief": "关键观察：把各行构造成单位排列的循环移位即可。用反转三段模拟循环移位，公共的整行反转不必逐行输出，因此总操作数压到 2n 以内。",
            "primary_topic": "构造与贪心",
        },
        "2039C2": {
            "statement_brief": "给定 x 和 m，统计 1<=y<=m 中使 x XOR y 能被 x、y 之一整除的 y 的数量。",
            "transformed_statement": "把题目先看成：分别令 p=x⊕y，研究 p 是 x 的倍数或 y 的倍数时 y=p⊕x 的取值范围；XOR 无进位的上下界会把候选压缩到很短的区间。",
            "key_observations": [
                "若 p 是 x 的倍数，则 y=p⊕x，且 p⊕x<=p+x；所以 p<=m-x 的所有 x 的倍数都必然合法，超过 m+x 后都必然越界，中间至多检查两个倍数。",
                "若 p 是 y 的倍数且 x<y，则 p=x⊕y<2y，同时 p 不能等于 y，因而不可能是 y 的正倍数；所以这一类只需枚举 y<=x。",
                "若同时被 x、y 整除，则 p 是 lcm(x,y) 的倍数；当 x!=y 时 lcm(x,y)>=2max(x,y)，而 XOR 小于该上界，只剩 y=x 的重合情形。",
            ],
            "solution_brief": "关键观察：按“被 x 整除”“被 y 整除”拆分并去重。第一类用倍数区间 + 少量边界检查，第二类只枚举 y<=x，交集仅可能是 y=x，故总复杂度 O(x)。",
            "primary_topic": "数论与同余",
        },
        "2039C1": {
            "statement_brief": "简单版要求统计 1<=y<=m 且 y!=x 的数，使 x XOR y 是 x 或 y 的真因子。",
            "transformed_statement": "把题目先看成：x XOR y 若为正整数因子，必须小于被整除的数；当 y>=2x 时 XOR 的最高位已经超过 x 和 y 各自可能拥有的真因子范围。",
            "key_observations": [
                "正数 x、y 的 XOR 不等于 x 或 y，因此若它是某数的因子，就必须不超过该数的一半，最高二进制位也会更低。",
                "当 y>=2x 时，x⊕y 的最高位与 y 相同，所以不可能是 y 的真因子；同时 x⊕y>x，也不可能是 x 的因子。",
                "因此只需枚举 y<2x（再与 m 取最小），直接检查 (x⊕y) 是否整除 x 或 y。",
            ],
            "solution_brief": "关键观察：最高位排除所有 y>=2x 的候选，剩余范围长度 O(x)。逐个计算 p=x⊕y，并检查 x%p==0 或 y%p==0，即可在线性于 x 的时间内计数。",
            "primary_topic": "数论与同余",
        },
        "2039B": {
            "statement_brief": "给字符串 s，要求找一个非空子串 p，使 p 的不同非空子串数量为偶数；不存在则输出 -1。",
            "transformed_statement": "把题目先看成：只需检查长度 2 的相邻相同模式和长度 3 的三个互异字符模式；若都不存在，整个串只能是严格交替串，而其不同子串总数必为奇数。",
            "key_observations": [
                "长度 2 的串 aa 有 2 个不同非空子串，因此出现相邻相同字符时直接取这两个字符。",
                "若相邻字符都不同，长度 3 的 abc 有 6 个不同非空子串，因此出现三个连续两两不同字符时直接取这三个字符。",
                "若两种局部模式都不存在，字符串必为 ababab...；对任意长度小于 n 的子串，每个长度恰有两个，整串长度 n 的子串只有一个，总数为 2n-1，恒为奇数。",
            ],
            "solution_brief": "关键观察：扫描相邻位置找 aa，再扫描长度 3 找三字符互异；找到即可输出。两者都不存在时由结构推出字符串严格交替，任意子串总数为奇数，因此无解。",
            "primary_topic": "字符串",
        },
        "2035H": {
            "statement_brief": "给两个排列 a、b。一次操作选位置 i，把 i 左边和 i 右边的部分分别循环右移一格；要求至多 2n 次把 a 变成 b，或判断无解。",
            "transformed_statement": "把题目先看成：先把 b^{-1}(a) 排成一种“半排序”状态，即 n 固定在末尾，其余只允许若干互不相交的相邻交换，再用末段操作收尾。",
            "key_observations": [
                "长度为 2 的排列 [2,1] 在任何操作下都不变，因此这是基本不可行情形；一般可达性最终归结为目标相对排列不能落入这个不动障碍。",
                "从最大值向最小值处理：若元素 x 不在末位，在其后一个位置操作即可把 x 插到当前前缀最前；若 x 在末位，则先移动 x-1，再用一次操作处理 x。",
                "这样至多 n+1 次得到半排序状态：n 在末尾，剩余乱序只表现为互不相交的相邻交换；随后用位置 n 或 n-1 的操作逐个修正，额外至多 n-1 次。",
                "模拟需要支持按位置操作、按值找位置和按位置取值，可用隐式平衡树，或维护时间减位置的索引实现摊还 O(1)。",
            ],
            "solution_brief": "关键观察：构造过程按值从大到小把元素送入已整理前缀，先在 n+1 步内压到半排序形态，再用末尾两种操作消除相邻交换；总操作不超过 2n，n=2 的反转状态单独判不可达。",
            "primary_topic": "构造与贪心",
        },
        "2256A": {
            "statement_brief": "黑板上有三个非负整数。每次可把其中一个替换为另外两个数之和，求操作任意次后三个数的最小极差。",
            "transformed_statement": "把题目先看成：不操作时得到初始极差；一旦操作，保留下来的两个数 u<=v 与 u+v 组成新状态，极差恰好是 v，而中位数无法下降。",
            "key_observations": [
                "排序为 a<=b<=c 后，不操作的极差是 c-a。",
                "进行一次操作并保留 u<=v 时，新三个数为 u、v、u+v，极差等于 v；之后每次操作后的中位数都不会低于当前中位数，因此所有非空操作序列的极差至少为初始中位数 b。",
                "把 c 替换成 a+b 就能得到 a、b、a+b，极差正好为 b，达到这个下界。",
            ],
            "solution_brief": "关键观察：两条候选路径分别是不操作得到 c-a，或一次把最大数换成 a+b 得到 b；中位数单调不降证明任何非空操作都不可能低于 b，所以答案为 min(c-a,b)。",
            "primary_topic": "构造与贪心",
        },
        "2217B": {
            "statement_brief": "给二进制数组和一个特殊位置 p。每次必须翻转包含 p 的区间，求把所有元素变成 p 处原始值所需的最少操作次数。",
            "transformed_statement": "把题目先看成：只记录目标值与当前值是否相同；翻转区间只会改变区间两侧的变化边界，而包含 p 的约束要求每次最多配掉左边一个边界和右边一个边界。",
            "key_observations": [
                "在数组首尾补上目标值后，定义相邻位置不同为一个边界；翻转 [l,r] 只会切换 l-1 和 r 两个边界。",
                "因为区间必须包含 p，一个被切换的边界在 p 左侧，另一个在 p 右侧，因此一次操作最多消除两侧各一个边界。",
                "左侧边界数为 x1、右侧边界数为 x2 时，先两两配对，再单独处理多出来的一侧，最少操作数正好是 max(x1,x2)。",
            ],
            "solution_brief": "关键观察：把数组压成 0/1 段并统计特殊位置两侧的边界数。每次操作可以配掉左右各一个边界，剩余边界只能单独消除，因此答案为 max(左边界数, 右边界数)。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2209E": {
            "statement_brief": "定义 f(t) 为字符串 t 能被拆成的最多段数，要求每段都是 t 的非空前缀。给定字符串 s，回答每个区间 [l,r] 中所有前缀子串 s[l..j] 的 f 值之和。",
            "transformed_statement": "把题目先看成：一个字符串的最优拆分由 border 链决定；反复去掉最短 border，直到剩下无 border 的串，就得到唯一的最优前缀拆分。",
            "key_observations": [
                "若字符串有 border，则它的最短 border 一定无 border；否则该 border 的更短 border 也会成为原串的 border，产生矛盾。",
                "任意最优拆分中的每一段都可以继续拆成无 border 的前缀，因此最优拆分等价于拆成无 border 前缀。",
                "无 border 前缀拆分是唯一的，最后一段必须是当前串的最短 border；所以不断裁掉最短 border 就能确定整个拆分。",
                "对每个前缀用 KMP 的最长 border 链求最短 border b_i，再有 f_i=1（无 border）或 f_{i-b_i}+1；每个查询独立线性处理即可。",
            ],
            "solution_brief": "关键观察：border 具有传递的嵌套结构，最短 border 递归决定唯一最优拆分。先由前缀函数沿 border 链求每个前缀的最短 border，再用 f_i=f_{i-b_i}+1 递推区间子串的答案，复杂度满足 O(nq)。",
            "primary_topic": "字符串",
        },
        "2183H": {
            "statement_brief": "把数组划分成恰好 k 个非空子序列，每个元素只能属于一个子序列；长度为 m、元素和为 S 的子序列代价为 mS，求总代价最小值。",
            "transformed_statement": "把题目先看成：先排序，再把问题变成连续分段；代价给每段所有元素乘上该段长度，因此交换相邻两段元素和长度可以导出长度单调性。",
            "key_observations": [
                "排序后可将最优划分规范化为排序数组上的连续段：两个值域相交的段若长度顺序不对，把较小元素交给较长段会降低加权和。",
                "因此各段长度满足 l_1>=l_2>=...>=l_k；固定切分点时，区间 [l,r] 的代价是 (r-l+1)*(前缀和差)。",
                "全为非负数时区间代价满足四边形不等式，分段 DP 的决策点单调，可用 Knuth 优化；含负数时，负数最优地集中在第一段，剩余正数再分段。",
                "大数据范围下给每段增加统一罚值，用 Alien trick 二分段数，再以决策单调性配合单调队列优化一维 DP；不能作为转移源的负数前缀需跳过。",
            ],
            "solution_brief": "关键观察：排序和交换论证把任意子序列划分压成长度非增的连续分段，代价变为区间和乘区间长度。小规模可做分段 DP；完整做法对段数加罚值二分，并在满足四边形不等式的受限转移上用单调队列，得到 O(n log n log V) 级复杂度。",
            "primary_topic": "动态规划与状态设计",
        },
        "2176B": {
            "statement_brief": "给一个至少含一个 1 的环形二进制串。一次操作选择环形右移 d 位，把移位后为 1 的位置在原串中设为 1，代价为 d；求把所有位置变成 1 的最小总代价。",
            "transformed_statement": "把题目先看成：每个环形连续 0 段的最右端都要被某个原有 1 传播到，传播代价至少覆盖该段长度；因此只需关注最长 0 段。",
            "key_observations": [
                "每次取 d=1，相当于让每个 0 段的左端 1 向右推进一格；重复最长 0 段长度 M 次即可填满所有 0。",
                "对长度为 M 的最长 0 段，紧邻其左侧的 1 在所有操作中最多向右移动总代价 S 格；若 S<M，该段最右端仍不可能变成 1。",
                "上界和下界相同，所以答案就是环上最长连续 0 段长度；把字符串复制一遍后扫描最长连续 0 段即可。",
            ],
            "solution_brief": "关键观察：总代价正好等于环上最长连续 0 段的长度。用 d=1 重复该次数达到上界，再用最长零段中最右端的传播距离给出下界。",
            "primary_topic": "字符串",
        },
        "2139A": {
            "statement_brief": "给两个正整数 a、b。一次操作可以把其中一个数乘以任意正整数，求把两数变相等所需的最少操作次数。",
            "transformed_statement": "把题目先看成：目标公共值可以选为原数之一，也可以直接选为 ab；因此只需判断相等、整除和一般情况。",
            "key_observations": [
                "若 a=b，不需要操作。",
                "若 a 能被 b 整除，直接把 b 乘以 a/b；反之亦然，所以整除时恰好一步。",
                "否则先把 a 乘 b 得 ab，再把 b 乘原来的 a 得 ab，始终两步可行；前两种情况已经证明不能更少。",
            ],
            "solution_brief": "关键观察：按 a=b、a|b 或 b|a、其余三种情况判断，答案分别为 0、1、2；一般情况用公共倍数 ab 给出两步构造。",
            "primary_topic": "数论与同余",
        },
        "2119D": {
            "statement_brief": "枚举所有满足 0<=a_i<=i 的序列。按序列 a 的指令从数轴点 1..n 中删除 token，f(a) 是可选删除方式数；求所有合法序列的 f(a) 之和。",
            "transformed_statement": "把题目先看成：先固定最终会被删除的 token 位置，再数每次指令能为它选择的左右端点；按从右到左的删除位置组织状态即可避免枚举全部序列。",
            "key_observations": [
                "若被删除的 token 位置按 p_0>p_1>...>p_{k-1} 排列，则对应的可行指令数乘积为 ∏ p_i*(n-p_i+1-i)：左端点有 p_i 种，右端点要避开已占用选择。",
                "因此只需统计所有递减位置集合的这个乘积，而不是逐个枚举每个 a_i 或删除过程。",
                "令 f_{i,j} 表示处理到右侧 i 个位置、已选 token 数为 i-j 的总和；当前位置选入或不选入分别产生 f_{i-1,j-1} 与 (n-i+1)(j+1)f_{i-1,j}。",
                "最后对 f_{n,j} 求和即可；状态转移是 O(n^2)，与题目给出的 n^2 总限制匹配。",
            ],
            "solution_brief": "关键观察：把删除过程按最终 token 位置重排后，每组位置的权重分解成独立乘积，再按从右向左选择位置做二维 DP。转移为 f_{i,j}=f_{i-1,j-1}+(n-i+1)(j+1)f_{i-1,j}，答案是末层总和。",
            "primary_topic": "组合计数与概率",
        },
        "2118C": {
            "statement_brief": "数组的 beauty 是所有元素二进制表示中 1 的总数。每次可把一个元素加 1，至多操作 k 次，求能达到的最大 beauty。",
            "transformed_statement": "把题目先看成：对一个数增加 beauty 的最便宜方式，是把最低位的 0 变成 1；因此把每个二进制位的这种“升级费用”汇总后贪心购买。",
            "key_observations": [
                "对整数 x，严格大于 x 且 beauty 更大的最小数，是把 x 最低位的 0 置为 1；到达它之前不会出现更高 beauty。",
                "这个最低位 0 的价值为 2^j，付出该差值恰好使 beauty 增加 1，低位的进位不会带来更便宜的替代方案。",
                "统计所有元素在每个二进制位上的 0 个数，从低位到高位依次购买升级；只要剩余 k 足够，就把该位的一个 0 变成 1。",
            ],
            "solution_brief": "关键观察：每次 beauty +1 的最小代价由当前最低位 0 决定，代价为对应的 2 的幂。统计各位可升级次数并从低位到高位贪心消耗 k，累计初始 beauty 和升级次数。",
            "primary_topic": "构造与贪心",
        },
        "2113D": {
            "statement_brief": "玩家和庄家各有 n 张不同数值的牌，按顶部顺序进行 n 轮比较，胜者得分且胜牌离场，负牌回到自己手牌顶部。玩家最多交换自己手中的两张牌一次，求最大得分。",
            "transformed_statement": "把题目先看成：玩家牌序列中的前缀最小值控制一整段胜负；若某个前缀最小牌能击败庄家当前牌，则它后面直到下一个前缀最小值的牌也都能赢。",
            "key_observations": [
                "记录玩家序列的所有前缀最小值及其位置；一个前缀最小值获胜时，同一块中的后续牌名义值都更大，也会在对应轮次获胜。",
                "因此固定一个玩家前缀长度后，胜负模拟只需用该前缀的最小值和剩余后缀的最大值交换，候选答案具有单调性。",
                "对能取得至少 x 分进行二分，再线性模拟该 x 的可行性，就能找到最大得分；前缀最小值分块避免逐轮尝试所有交换位置。",
            ],
            "solution_brief": "关键观察：前缀最小值把玩家牌序列分成若干可整体判断的块，固定可赢前缀长度后用“前缀最小值换后缀最大值”检验。可行得分单调，二分答案并模拟即可。",
            "primary_topic": "构造与贪心",
        },
        "2108B": {
            "statement_brief": "构造长度为 n 的正整数数组，使所有元素 XOR 为 x，并在所有可行数组中最小化元素和；只输出最小和。",
            "transformed_statement": "把题目先看成：x 的每个 1 位至少要由一个对应的二进制块承担；块数不够时直接拆成互异幂，块数多出来则用 1 填充并只修正 XOR 奇偶。",
            "key_observations": [
                "当 x>1 时，x 的二进制中每个 1 位对应一块互异的 2 的幂，块数 popcount(x) 不超过 n 时总和下界就是 x。",
                "若 n 超过这些块数，多出的元素最便宜只能取 1；多出的 1 的奇偶性若不对，就把某个幂块拆成 2 和 3（XOR 为 1）补一次奇偶。",
                "x=1 时，n 为奇数可全取 1；n 为偶数需要额外使用 2、3 这一对。x=0 时，偶数个 1 可直接使用，奇数个元素用 1、2、3 这一组三元组，n=1 无解。",
            ],
            "solution_brief": "关键观察：先用 x 的置位数判断能否把 x 拆成若干互异幂；额外位置用 1，必要时只增加一个奇偶修正块。特殊处理 x=0、1 的最小正数 XOR 构造即可 O(1) 求答案。",
            "primary_topic": "数论与同余",
        },
        "2107A": {
            "statement_brief": "把数组划分成两个非空序列 B、C，要求 gcd(B) 与 gcd(C) 不相等；判断是否可行并给出任意划分。",
            "transformed_statement": "把题目先看成：把所有最大值单独放一组，其 gcd 恰为最大值；只要数组不全相同，另一组的 gcd 必然严格更小。",
            "key_observations": [
                "若所有元素都相同，任意非空子集的 gcd 都是该值，因此不可能。",
                "否则令 mx=max(a)，把所有等于 mx 的元素放入一组，其 gcd 为 mx；把其余元素放入另一组。",
                "另一组至少含一个小于 mx 的元素，而一组数的 gcd 不超过其中最小元素，所以另一组 gcd 严格小于 mx。",
            ],
            "solution_brief": "关键观察：全相同是唯一无解情形。找到最大值后按“是否等于最大值”二分数组，两个非空组的 gcd 自动不同。",
            "primary_topic": "数论与同余",
        },
        "2061H1": {
            "statement_brief": "给无向图、初始放置石子的顶点集合和目标顶点集合。每轮所有石子同时沿一条相邻边移动，且任意时刻一个顶点至多放一枚石子；判断是否存在合法移动序列到达目标。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是一个带同步移动和无碰撞约束的图上石子可达性判定题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "图论与网络流",
        },
        "2048H": {
            "statement_brief": "给一个二进制串。每次选择位置 p，先对 p 左侧所有位置同时执行 t_i=max(t_i,t_{i+1})，再删除第 p 个字符；求经过任意次操作后能得到的不同非空二进制串数量。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：操作同时传播左侧的 1 并删除一个位置，目标是统计所有可达字符串的去重数量。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "字符串",
        },
        "2048G": {
            "statement_brief": "统计 n×m、元素取自 1..v 的整数矩阵中，满足 min_i(max_j a_i,j) <= max_j(min_i a_i,j) 的矩阵数量，结果对 998244353 取模。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是比较“最弱行最大值”和“最强列最小值”的矩阵计数题，需统计满足该极值不等式的全部矩阵。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2029A": {
            "statement_brief": "给集合 S={l,l+1,...,r} 和整数 k。每次可以删除一个 x，前提是当前集合中至少有 k 个 x 的倍数（包括 x）；求最多能删除多少次。",
            "transformed_statement": "把题目先看成：按从小到大删除时，被删的小数不可能影响更大的候选；x 可删当且仅当初始区间里至少有 k 个 x 的倍数。",
            "key_observations": [
                "从小到大删除不会破坏后续判断：若 x<y，x 不可能是 y 的倍数，因此删除 x 不会减少 y 的倍数。",
                "对 x，区间 [l,r] 中的倍数数量至少为 k 当且仅当第 k 个倍数 kx 不超过 r，即 x<=floor(r/k)。",
                "所有满足 l<=x<=floor(r/k) 的数都能依次删除，超过该范围的数一开始就不满足条件。",
            ],
            "solution_brief": "关键观察：小数优先删除把动态条件固定成初始倍数计数；可删元素恰为区间 [l,floor(r/k)]，答案为 max(floor(r/k)-l+1,0)。",
            "primary_topic": "数论与同余",
        },
        "2021C1": {
            "statement_brief": "简单版中，队伍成员按数组 a 排队，按数组 b 指定每张幻灯片的讲解者；每次讲完后只能把队首成员移到队列任意位置。判断整个演示是否可完成。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是一个队首取出、再任意插回的序列可行性判定题；简单版没有持久更新。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2226B": {
            "statement_brief": "若数组最大值减最小值等于全体元素的 gcd，则称其为 good。给一个排列，求其中 good 子数组的数量。",
            "transformed_statement": "把题目先看成：除以全体 gcd 后，最大值和最小值必须是相邻整数；排列元素互异又迫使 good 子数组只能有长度 2。",
            "key_observations": [
                "设全体 gcd 为 g，最大值为 Mg、最小值为 mg。good 条件化为 M-m=1，因此数组只能含相邻的两个 gcd 倍数值。",
                "给定的是排列，子数组内元素互不相同；长度不是 2 时不可能只有上述两个值，所以只需检查相邻二元组。",
                "对相邻值 u,v，条件可直接写成 max(u,v)-min(u,v)=gcd(u,v)，等价于较大值对差值整除。",
            ],
            "solution_brief": "关键观察：gcd 归一化把 good 化成“只有相邻的两种值”，排列性进一步把候选缩到长度 2；线性检查每个相邻对即可。",
            "primary_topic": "数论与同余",
        },
        "2124D": {
            "statement_brief": "每次可在长度至少 k 的子数组中删除一个等于该子数组第 k 小值的元素；问能否经过若干次删除把数组变成回文。",
            "transformed_statement": "把题目先看成：全局第 k-1 小的元素构成不可删除的保底层；更大的元素都能先删掉，剩下只需在临界值两侧做最少删除的双指针配对。",
            "key_observations": [
                "只要数组中最小的 k-1 个元素仍保留，任意其它元素都可以通过逐步收缩区间，使它成为某个区间的第 k 小值并删除。",
                "令 x 为全局第 k-1 小值；大于 x 的元素没有保留价值，可先全部删除，得到只含 <=x 的序列。",
                "对剩余序列从两端比较：相等就保留；不等时，只有等于 x 的一端可以删除，两个都小于 x 则无法修复。",
                "删除 x 的次数不能超过可牺牲的元素数量，否则会连保底的 k-1 个元素也删掉；最后检查剩余长度至少 k-1。",
            ],
            "solution_brief": "关键观察：先用第 k-1 小值把元素分为可任意删除的“大数”和需要保留的“小数/临界值”，再对过滤后的序列双指针；冲突时只删临界值，并检查剩余保底数量。",
            "primary_topic": "构造与贪心",
        },
        "2119A": {
            "statement_brief": "给非负整数 a、b，以及加一代价 x、按位异或 1 代价 y；可以任意使用两种操作，把 a 变成 b，求最小代价或判断无解。",
            "transformed_statement": "把题目先看成：异或 1 只会在偶数处把数加 1、在奇数处把数减 1；先处理 b<a 的单步特殊情况，之后沿 a 到 b 的奇偶路径选择便宜操作。",
            "key_observations": [
                "若 b<a，唯一可能是一次 a⊕1=b；否则两种操作都无法降低到目标，直接无解。",
                "当 a<=b 时，加一每次都能前进；异或 1 只有当前数为偶数时才前进，作用是从偶数跳到下一个奇数且不改变更高位。",
                "因此从 a 到 b 的路径固定，前进步数中偶数起点和奇数起点的数量由 a、b 的奇偶决定；偶数起点的步可以取 min(x,y)，奇数起点只能付 x。",
            ],
            "solution_brief": "关键观察：把 XOR 1 解释为“偶数加一、奇数减一”。先判 b<a 的单步/无解情形，再按路径上偶数步与奇数步的数量，用较便宜的操作替换偶数步，O(1) 得最小代价。",
            "primary_topic": "数论与同余",
        },
        "2085B": {
            "statement_brief": "反复选择数组中的一个子数组，用其 MEX 替换整段，直到只剩一个数；要求最后的数为 0。",
            "transformed_statement": "把题目先看成：最后一次对全数组取 MEX 要得到 0，因此最后一次之前所有元素必须非零；先把含 0 的两半各自压成非零，再整体合并。",
            "key_observations": [
                "一个集合的 MEX 为 0 当且仅当其中不含 0，所以最后一步必须面对一个全为正数的数组。",
                "把原数组分成左右两半；哪一半含 0 就对哪一半做一次 MEX 压缩，压缩后的值不为 0，从而消除该半段中的 0。",
                "此时整个数组没有 0，对全数组做最后一次操作即可得到 MEX=0；n>4 时也可以先压到长度 4 再暴力处理。",
            ],
            "solution_brief": "关键观察：把“最后取 MEX 得 0”倒推成“最后前不能有 0”。按左右两半分别消除 0，再对剩余全数组取一次 MEX；整个构造只需常数次操作。",
            "primary_topic": "构造与贪心",
        },
        "2061E": {
            "statement_brief": "数组中每个元素都可以至多 k 次与给定魔法数 b_j 做按位 AND，求操作后数组元素和的最小值。",
            "transformed_statement": "把题目先看成：对固定一个元素，使用若干不同魔法后的最小值序列具有离散凸性；全局只需把所有单步边际下降按大小选出。",
            "key_observations": [
                "对一个初值 p，定义使用恰好 j 个不同魔法后的最小结果 num(p,j)；题解证明其最优值关于 j 的离散差分单调不增。",
                "因此该元素从 j-1 次增加到 j 次的下降量具有先大后小的结构，不能把同一元素的后续下降孤立看成任意独立收益。",
                "但所有元素的边际下降都可合并：总共选 k 个最大的下降量，就得到全局最小和；每个 num(p,j) 可枚举魔法子集求出。",
            ],
            "solution_brief": "关键观察：按位 AND 子集最优值对操作数呈离散凸性，所以每个元素的边际收益单调；枚举每个元素的子集结果，收集所有边际下降并取最大的 k 个即可。",
            "primary_topic": "动态规划与状态设计",
        },
        "2056B": {
            "statement_brief": "给出由隐藏排列生成的无向图邻接矩阵：若排列中较小值 x 出现在较大值 y 之前，就在 x、y 对应顶点间连边；要求恢复唯一排列。",
            "transformed_statement": "把题目先看成：对任意 x<y，邻接矩阵的一位就直接告诉 x 是否排在 y 前面，因此矩阵行列编码了一个可比较的全序。",
            "key_observations": [
                "若 x<y 且 x 在排列中位于 y 之前，则按构图规则 g_{x,y}=g_{y,x}=1；反之两位都为 0。",
                "所以对任意一对数，g_{x,y}=1 就把 x 排在 y 前，否则把 y 排在 x 前；这给出了完整比较器。",
                "用这个比较器对 1..n 排序即可恢复排列，题目保证输入确实来自某个排列，因此比较关系一致。",
            ],
            "solution_brief": "关键观察：邻接矩阵不是普通图结构，而是直接编码任意两值的先后关系。把 g_{x,y} 转成比较器后排序所有顶点即可。",
            "primary_topic": "图论与网络流",
        },
        "2056C": {
            "statement_brief": "构造长度为 n、元素在 1..n 的数组，使最长回文子序列的数量超过 n。",
            "transformed_statement": "把题目先看成：先固定两端形成一个短回文，再把中间任意位置作为中心插入；要让最长长度不被抬高，只需让其它端点组合不能形成更长回文。",
            "key_observations": [
                "若两端选出的序列已经是回文，那么在其两端之间插入任意一个元素会得到奇数长度回文，因为插入元素正好位于中心。",
                "构造 [1,2,3,...,n-2,1,2] 时，最长回文长度为 3；以 (1,1) 或 (2,2) 为两端、任取中间位置都能产生大量长度 3 的回文子序列。",
                "长度 3 的最长性来自前缀中各值的安排，避免出现更长的对称端点；n=6 等小边界单独使用题解给出的构造。",
            ],
            "solution_brief": "关键观察：用重复的端点制造大量可选中心，同时控制最长回文长度。通用构造为 1..n-2,1,2，n=6、少数特殊长度用固定构造，保证回文数量超过 n。",
            "primary_topic": "字符串",
        },
        "2250A": {
            "statement_brief": "每个位置的元素同时向左或向右移动一格：权值小于阈值 k 向左，大于 k 向右，等于 k 则失败。要求移动后 1..n 每个位置仍恰有一个元素，判断是否存在整数 k。",
            "transformed_statement": "把题目先看成：位置 1 只能由位置 2 补回，因此所有元素必须成对交换；奇数位向右、偶数位向左，阈值要严格夹在两类权值之间。",
            "key_observations": [
                "位置 1 的元素不能向左，只能向右；为了填满位置 1，位置 2 必须向左，于是前两位必须交换。重复此论证，所有位置按 (1,2)、(3,4) 成对交换。",
                "因此 n 必须为偶数，奇数位置权值必须大于 k，偶数位置权值必须小于 k，且不能有权值等于 k。",
                "令 L 为偶数位权值最大值、R 为奇数位权值最小值，需要整数 L<k<R；存在性等价于 L+2<=R。",
            ],
            "solution_brief": "关键观察：同步移动的满占条件唯一强制出相邻成对交换模式。扫描奇偶位置的权值范围，检查 n 为偶数且 max(偶数位)+2<=min(奇数位)。",
            "primary_topic": "构造与贪心",
        },
        "2202G1": {
            "statement_brief": "从全白 n×n 矩阵开始，依次把指定格子染黑；每次染色后判断矩阵是否存在两行两列形成交叉同色、且同列异色的禁形。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是一个黑格逐步加入的矩阵禁形在线判定题，简单版规模较小。",
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
        "2201F1": {
            "statement_brief": "中等版同样从全白 n×n 矩阵开始，持久地把查询指定的格子染黑，并在每次操作后判断是否出现题目定义的四格禁形；规模更大。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是与 简单版相同的在线单调矩阵禁形判定问题，只是 n、q 更大。",
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2174E1": {
            "statement_brief": "交互题。隐藏整数 x∈[1,c]，询问一个进制 b：若 x<b 返回 -1，否则返回 x 在 b 进制下的数位和；要求在至多 k=4 次询问内猜出 x。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：通过不同进制下的数位和与 x<b 的边界反馈恢复隐藏整数，属于非自适应交互查询问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写交互策略。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2158F1": {
            "statement_brief": "构造长度为 n 的正整数序列，使相邻元素的 gcd 两两不同，并让序列中不同元素的种类数尽可能少；简单版 n≤700。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：需要同时满足相邻 gcd 的全异约束和使用不同数值种类数的最小化。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写构造。",
            "extraction_status": "missing_editorial",
            "primary_topic": "数论与同余",
        },
        "2140A": {
            "statement_brief": "给二进制串，每次选三个位置并把这三个值循环左移或右移；求把串排序成所有 0 在前、1 在后的最少操作数。",
            "transformed_statement": "把题目先看成：排序目标的前 cnt0 个位置应为 0，统计其中错放的 1；一次三点循环移位可以同时修正一个错放的 1 和一个错放的 0。",
            "key_observations": [
                "设 cnt0 为串中 0 的总数，目标串的前 cnt0 位必须全为 0；其中出现的 1 就是错位的 1，数量记为 M。",
                "错位的 1 与错位的 0 数量相等；若选它们作为三点中的两点，第三点可取两点之间或外侧的合适位置，循环移位能把端点变成 0、1。",
                "每次操作至多修正一对错位元素，而上述构造总能一次修正一对，因此最少操作数正好是 M。",
            ],
            "solution_brief": "关键观察：答案不是逆序对，而是目标前缀中的错位 1 数。每次三点循环移位可同时修正一个错位 1 和一个错位 0，上下界相等，线性统计即可。",
            "primary_topic": "构造与贪心",
        },
        "2078A": {
            "statement_brief": "每次把数组均分成若干个等长子序列，并用各子序列平均值组成新数组，直到只剩一个数；判断最终能否得到给定的 x。",
            "transformed_statement": "把题目先看成：每次新数组的总和等于旧数组总和的平均化结果，整体平均值在所有操作中保持不变；最终单元素只能等于初始平均值。",
            "key_observations": [
                "把数组划分为等长子序列后，新数组元素之和等于原数组元素总和除以每组长度，再乘组数，恰好与原数组平均值相同。",
                "因此整个数组的平均值是操作不变量；当数组缩到长度 1 时，唯一元素必须等于初始平均值。",
                "反过来，若初始平均值等于 x，直接选择 k=1 的合法合并路径即可得到 x；所以只需检查 sum(a)=n*x。",
            ],
            "solution_brief": "关键观察：平均值在每次等长分组取平均后不变，最终单元素只能是初始平均值。判断数组和是否等于 n*x 即可。",
            "primary_topic": "组合计数与概率",
        },
        "2077G": {
            "statement_brief": "在三色带权图中从 1 走到 n，可重复经过边；记三种颜色边的总权重为 s_r、s_g、s_b，求最小化 max(s)-min(s)。",
            "transformed_statement": "把题目先看成：先利用往返走边制造可调的颜色总量，再只保留每种颜色模 2gcd 的 0/ gcd 两类状态，最后在八种状态中解三组同余并最小化跨度。",
            "key_observations": [
                "沿任意边走到端点再原路返回会让该边被经过偶数次，因此可以构造回到 1 且三色差值全为 0 的闭 walk；再往返走边可按每种颜色的 2 倍 gcd 调整总量。",
                "对颜色 c，任何可达总量只需记录它模 2g_c 的余数是 0 还是 g_c，其中 g_c 是该颜色所有边权的 gcd；三种颜色合起来每个顶点只有 2^3 个状态。",
                "从 1 到 n 的每个可达状态对应三组同余约束 d_c≡s_c (mod 2g_c)；固定哪一种颜色达到最小值后，其余两种颜色的最小上方距离可按模 gcd 分组，并用 CRT 合并。",
                "在状态图上求出可达的八种状态，枚举每种最小颜色和余数类，取 max(s)-min(s) 的最小值；复杂度由图遍历、gcd 和权值上界共同决定。",
            ],
            "solution_brief": "关键观察：颜色总量的绝对值不重要，往返走边后只需保留三个模 2gcd 的二元状态。建 8 状态扩展图找可达状态，再用 CRT 处理剩余同余约束并求最小跨度。",
            "primary_topic": "数论与同余",
        },
        "2056F2": {
            "statement_brief": "困难版要求对所有长度为 n、元素在 [0,m) 且各值出现次数非降的好序列，计算这些序列的中位数按位 XOR。n 以二进制形式给出。",
            "transformed_statement": "把题目先看成：排列顺序只贡献多项式系数的奇偶性；Lucas 定理把奇数贡献筛成“n 的二进制置位被各计数无进位分配”，最大计数对应的值必是中位数。",
            "key_observations": [
                "固定每个值的出现次数 cnt 后，所有排列数是多项式系数；由 Lucas 定理，该系数为奇数当且仅当 n 的每个置位恰好被某个 cnt_i 独占，即计数之和是无进位加法。",
                "无进位分配中拥有 n 最高置位的那个 cnt_i 满足 2*cnt_i>n，因此对应的值一定落在中位数位置；问题转化为按非零计数个数 p 和中位数 x 统计奇偶贡献。",
                "将 n 的置位分成 p 个非空组有第二类 Stirling 数 S(b,p) 种方式；非降计数又把其它非零值限制成从 x 以下选择 p-1 个，贡献出现二项式系数的奇偶性。",
                "困难版再次用 Lucas 定理把对所有 p 的异或改写成 x 的低位子掩码和，用 SOS DP 求每种低位模式是否贡献，再按区间块计算小于 m 的 x 的 XOR。",
            ],
            "solution_brief": "关键观察：先用 Lucas 定理筛掉偶数多项式系数，再证明最大计数位置就是中位数；计数结构归结为第二类 Stirling 数和二项式系数的奇偶。困难版对低位子掩码做 SOS DP，从而处理超大 n 的二进制输入。",
            "primary_topic": "组合计数与概率",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2029B": {
            "statement_brief": "给二进制串 s 和长度为 n-1 的替换串 r。第 i 步必须选一对相邻且不同的字符，把这两个字符替换成 r_i；问能否完成全部操作。",
            "transformed_statement": "把题目先看成：可操作性只取决于当前串是否同时含有 0 和 1；每次替换只是在两种字符计数中删掉其中一种。",
            "key_observations": [
                "二进制串存在相邻不同字符，当且仅当串中同时存在 0 和 1；否则无论怎么选都无法操作。",
                "每次操作一定删掉一个 0 和一个 1；若新字符是 0，则 0 的数量不变、1 的数量减一，若新字符是 1 则反过来。",
                "所以无需关心字符排列，只需在每步开始前检查两种字符数量是否都非零，并按 r_i 更新计数。",
            ],
            "solution_brief": "关键观察：相邻不同对的存在等价于两种字符都还存在。维护 0 和 1 的数量，遇到某一类提前耗尽就失败，否则按替换字符更新数量并完成模拟。",
            "primary_topic": "博弈",
        },
        "2022D1": {
            "statement_brief": "交互题。多人中恰有一名冒名者，需要通过询问两个人之间的判断关系，在 n+69 次询问内找出冒名者。",
            "transformed_statement": "把题目先看成：两两互问可以把大多数人安全删掉；只有互问结果不一致时，冒名者才一定落在这两人之中。",
            "key_observations": [
                "询问 u 指向 v 和 v 指向 u 的答案相同，当且仅当 u、v 都不是冒名者；这个性质可由三种身份的真假话关系分类验证。",
                "因此可以每次拿最后两个人互问：若答案相同，就把二者一起排除；若不同，就把候选缩成这两人。",
                "候选缩成两人后，再拿其中一人与确定不在候选中的人互问，就能区分哪一个是冒名者；剩下 3 或 4 人时用固定小策略收尾。",
            ],
            "solution_brief": "关键观察：互问结果相同是一张“二者都安全”的证书。反复成对删除安全人；一旦出现不一致，用第三个非候选人做参照区分两名候选，查询数保持在线性范围内。",
            "primary_topic": "交互",
        },
        "2013F2": {
            "statement_brief": "树上两人从不同点出发轮流移动，不能走到任何已访问点，无法移动者输。给定不经过 1 的路径 u 到 v，要求分别判断 Bob 从路径上每个点出发时的胜者。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是一个树上双人移动博弈，对同一路径上的多个 Bob 起点批量输出胜负。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "树结构",
        },
        "2249A": {
            "statement_brief": "给 n 个按原顺序排列的元素，每个元素禁止某些左排名和右排名。可以删除任意元素，求剩余子序列的最大合法长度。",
            "transformed_statement": "把题目先看成：先猜最终长度 m；一旦 m 固定，第 j 个保留位置的左右排名都固定，问题就变成按原序贪心填满 m 个槽。",
            "key_observations": [
                "元素是否能放在第 j 个位置不仅取决于 j，也取决于最终长度 m，因为它的右排名是 m-j+1。",
                "固定 m 后，从左到右扫描原序列，能放入当前槽位就立刻放入；选更早的合法元素不会减少后续可用位置。",
                "交换论证：若某个可行方案在第 j 位选了更晚的元素，用贪心选到的更早元素替换它，后面所有选择仍然保留原相对顺序。",
            ],
            "solution_brief": "关键观察：枚举最终长度，把动态的右排名变成固定条件。对每个 m 贪心填槽，能填满则可行；从大到小枚举 m，第一个可行值就是答案。",
            "primary_topic": "构造与贪心",
        },
        "2239C": {
            "statement_brief": "给排列的部分约束：某些位置给出 p_i，某些位置给出前缀逆序数 s_i。要求恢复原排列。",
            "transformed_statement": "把题目先看成：已知前缀逆序数的位置把排列切成若干块；从后往前扣掉已确定元素的贡献，就能反推出当前关键位置的值。",
            "key_observations": [
                "相邻两个已知前缀逆序数的差，只来自新增区间内部的逆序，以及新增元素与左侧前缀之间的逆序。",
                "从后往前处理时，右侧和当前块内已经确定的值可以用树状数组统计并扣除，剩余量就是当前待定值在未用数字中的排名约束。",
                "题目保证有解，因此每次扣除后对应的未用数字是唯一的；用可求第 k 小的结构取出并标记即可。",
            ],
            "solution_brief": "关键观察：不要正向猜排列，而是把前缀逆序数差分后倒着还原。每处理一个带 s 约束的位置，就先减去已知逆序贡献，再按剩余排名从未用数字中选出唯一值。",
            "primary_topic": "数据结构",
        },
        "2220A": {
            "statement_brief": "要求重排数组，使任意位置的值都不能表示成它前面若干元素的子集和；若做不到输出 -1。",
            "transformed_statement": "把题目先看成：重复值会立刻制造单元素子集和；没有重复时，把数降序排列即可让前面任意非空子集和都大于当前数。",
            "key_observations": [
                "若存在两个相等元素，排在后面的那个总能被前面相同元素单独表示，因此必然被阻塞。",
                "若所有数互不相同且均为正数，按降序排列后，当前位置前面的每个数都严格大于当前数。",
                "于是前面任意非空子集和至少大于当前数，不可能恰好等于当前值。",
            ],
            "solution_brief": "关键观察：重复值是唯一障碍。先判重，存在重复直接无解；否则按从大到小输出，正数性保证所有前缀子集和都不会等于后面的较小元素。",
            "primary_topic": "构造与贪心",
        },
        "2215B": {
            "statement_brief": "定义一个数在进制 b 下若每 p 位一组且组内数字全相同，则称为一组有序参数下的整齐表示；给 n，求满足条件的有序参数对数量。",
            "transformed_statement": "把题目先看成：按重复块长度分类。块长为 2 时出现因子 b+1；块长至少为 3 时出现等比和因子，从而把可枚举范围压小。",
            "key_observations": [
                "块长为 2 时，每一对相同数字贡献 d(1+b)，所以整个 n 必须被 b+1 整除；枚举 n 的因子即可得到候选进制。",
                "块长至少为 3 时，每组相同数字都含因子 1+b+...+b^{p-1}，这个因子必须整除 n，并且立即给出 b^{p-1} 不超过 n 的上界。",
                "候选参数出来后仍需实际检查 n 在该进制下是否真的按 p 位重复，避免只靠整除条件误计。",
            ],
            "solution_brief": "关键观察：重复数字块会强制 n 含有固定的进制因子。块长 2 枚举 b+1 的因子；块长更大枚举小范围内的 b 和块长，并用进制展开检查是否合法。",
            "primary_topic": "数论与同余",
        },
        "2211D": {
            "statement_brief": "给未知数组 a 的按位与子序列和数组 b_k：所有长度为 k 的子序列按位与后求和。要求构造任意一个符合 b 的数组 a。",
            "transformed_statement": "把题目先看成：每个二进制位独立，只需要恢复这个位在多少个 a_i 中出现；恢复完各位频次后再随便安排到前若干个位置。",
            "key_observations": [
                "若某一位在 cnt 个元素中出现，那么它对 b_k 的贡献是 2^位号 乘以组合数 C(cnt,k)，因为长度 k 的子序列必须全选到含该位的元素。",
                "b_n 只可能包含那些出现在全部 n 个元素中的位；这些位确定后，可以从所有 b_k 中减去它们的组合贡献。",
                "减完后就不存在出现 n 次的位，把有效规模视为 n-1 重复处理；题目保证有解，所以每个位只会在某一层被删除一次。",
            ],
            "solution_brief": "关键观察：按位拆开后，b_k 是各位出现频次的组合数叠加。不断从最高长度 b_n 识别出现 n 次的位并扣除贡献，就能恢复每个位的频次；再把该位放进前 cnt 个数组元素中构造答案。",
            "primary_topic": "组合计数与概率",
        },
        "2211A": {
            "statement_brief": "给一个排列。每次选长度为 3 的子数组，删除其中最小值或最大值；对每个原元素，求仍保留它时能得到的最小数组长度。",
            "transformed_statement": "把题目先看成：长度小于 3 后无法继续操作，所以除 n=1 外答案至少为 2；关键是证明任意目标元素都能保到长度 2。",
            "key_observations": [
                "当数组长度为 1 时答案只能是 1；当长度为 2 时已经没有合法操作，因此一般下界是 2。",
                "想保留值 x 时，每次选一个包含 x 的三元子数组；若 x 是其中最小值就删除最大值，否则删除最小值。",
                "这样总能删除掉一个非 x 元素，重复直到只剩两个元素且 x 仍在其中。",
            ],
            "solution_brief": "关键观察：三元组操作总能避开目标元素删掉另一个极值，因此任意元素都能保留到长度 2。输出 n=1 时为 1，否则全为 2。",
            "primary_topic": "构造与贪心",
        },
        "2209B": {
            "statement_brief": "对每个位置 i，任选整数 k，最大化右侧满足 |a_i-k|>|a_j-k| 的位置数，输出每个 i 的最大值。",
            "transformed_statement": "把题目先看成：每个右侧元素只关心它在 a_i 的哪一侧；把 k 取到所有数很左或很右，就分别统计右侧更小值和更大值。",
            "key_observations": [
                "若 a_j 小于 a_i，要让 a_i 离 k 更远，需要把 k 放在二者中点左侧；若 a_j 大于 a_i，则需要把 k 放在中点右侧。",
                "两类条件分别要求 k 在 a_i 左侧或右侧，因此最优只会选择极小或极大的 k 来统一满足其中一类。",
                "于是对每个 i，答案就是右侧小于 a_i 的数量和右侧大于 a_i 的数量二者取最大。",
            ],
            "solution_brief": "关键观察：中间的 k 不会同时优于两端极值；把 k 放到最左只统计右侧更小值，放到最右只统计右侧更大值。逐对计数即可，也可用树状数组优化。",
            "primary_topic": "几何",
        },
        "2157G": {
            "statement_brief": "交互题。隐藏随机数组，询问区间异或值的最高位或是否为零；需要在有限代价内回答所有区间询问结果。",
            "transformed_statement": "把题目先看成：先转成前缀异或点集，区间询问变成两个前缀点的异或最高位；问题等价于恢复这些点在二进制前缀树中的相对分裂结构。",
            "key_observations": [
                "设前缀异或为 x_i，则原区间异或等于两个前缀点的异或；查询返回的最高位正好描述二者在二进制前缀树中从哪一层分开。",
                "在某个前缀树节点内，只要能把点按下一位分成 0、1 两组，就能递归处理两个子块；不影响查询答案的位可以统一设为 0。",
                "为了低代价完成分裂，只在该块的位置集合上选若干对询问；题解用边代价 1/区间长度 的最小生成树，并利用最优边常贴近块端点来简化实现。",
            ],
            "solution_brief": "关键观察：区间异或查询先化为前缀点两两异或的最高分裂位。递归构造前缀树，每层用少量成对询问把当前块按下一位切开；用最小生成树控制询问总代价，最后即可回答任意区间。",
            "primary_topic": "交互",
        },
        "2129C3": {
            "statement_brief": "交互题。隐藏括号串，询问由若干指定位置拼成的串中有多少非空合法括号子串；困难版要求在 100 次内恢复整串。",
            "transformed_statement": "把题目先看成：先找到一个左括号和一个右括号作参照，再把多个未知位置编码进同一次询问，使返回值的差分携带多位信息。",
            "key_observations": [
                "先二分找到某个出现合法括号子串的位置边界，由相邻两位得到一左一右；若整串没有普通前缀证据，则用首尾特殊情况处理。",
                "简单版中，可以把两个未知字符插入到固定括号模板里，使四种取值对应四个不同的返回值，从而一次确定两个位置。",
                "中等版把不同位置赋予二进制权重：比较模板基准值和实际询问值，差值的二进制位直接指出哪些位置是右括号。",
                "困难版把单个大权重模板拆成左右两段短模板，或用三角数权重满足前缀和分离条件，从而在长度限制内一次恢复约 12 个位置。",
            ],
            "solution_brief": "关键观察：询问值不是只判合法性，而是可以当成编码通道。先找参照括号，再用带权模板把一组未知位置压进一次询问，通过返回值差分解码；困难版优化模板长度后分批恢复整串。",
            "primary_topic": "交互",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2096A": {
            "statement_brief": "给 n 根长度互不相同且为 1..n 的木棍，以及长度 n-1 的符号串。若符号为 <，当前位置必须成为新的前缀最小值；若为 >，当前位置必须成为新的前缀最大值。构造任意合法排列。",
            "transformed_statement": "把题目先看成：从右往左决定每个位置。最后一个符号直接决定最后一根木棍取当前最小还是当前最大，取走后剩余前缀变成同样问题。",
            "key_observations": [
                "若 s_i 是 <，第 i+1 个位置必须小于前面所有数，所以在剩余数里取最小值最稳妥。",
                "若 s_i 是 >，第 i+1 个位置必须大于前面所有数，所以在剩余数里取最大值。",
                "从右往左每次拿走一个极值后，剩余可用长度仍是一段连续整数，只需维护左右端点。",
            ],
            "solution_brief": "关键观察：要求的是“成为当前前缀的新极值”。倒着扫符号串，遇到 < 就把当前最小值放到后一位，遇到 > 就放当前最大值，最后剩下的数放到第一位。",
            "primary_topic": "构造与贪心",
        },
        "2085E": {
            "statement_brief": "给数组 a 和被打乱后的数组 b，要求找一个整数 k，使 b 恰好是所有 a_i 对 k 取余后的多重集合；不存在则输出 -1。",
            "transformed_statement": "把题目先看成：若 k 合法，则总和差 Δ=sum(a)-sum(b) 必须是 k 的倍数；当 Δ=0 时，只可能选择大于所有 a_i 的 k，让取余后数组不变。",
            "key_observations": [
                "每个 a_i 与它的余数之差都是 k 的倍数，打乱不会改变总和，所以 Δ 也必须被 k 整除。",
                "若 Δ=0，合法 k 必须让每个 a_i 取余后仍等于自身；选一个大于所有 a_i 的固定大数，再检查多重集合即可。",
                "若 Δ>0，只需枚举 Δ 的所有因子作为候选 k，并逐个检查取余后的多重集合是否等于 b。",
            ],
            "solution_brief": "关键观察：魔法数一定整除总和差。先处理 Δ<0 和 Δ=0 的边界；Δ>0 时枚举因子，用计数数组验证 {a_i mod k} 与 b 的多重集合是否相同。",
            "primary_topic": "数论与同余",
        },
        "2035A": {
            "statement_brief": "n×m 的队列按行优先编号，某个位置的人离开后，所有编号更大的人依次补到前一个人的原位置；求所有移动的曼哈顿距离之和。",
            "transformed_statement": "把题目先看成：编号小于离开者的人完全不动；后面的人只会左移一格，只有每一行行首的补位会从下一行跨到上一行末尾。",
            "key_observations": [
                "离开位置之后，同一行内的补位每人距离为 1。",
                "从第 r+1 行到第 n 行，每行第一个需要跨到上一行末尾，距离为 m；这样的跨行人数有 n-r 个。",
                "剩下所有受影响的人都只在同一行相邻移动一次，数量可由总后缀长度减去跨行人数得到。",
            ],
            "solution_brief": "关键观察：移动只有两种代价：跨行补位代价 m，同一行左移代价 1。统计离开者之后的人数，再把每个后续行首作为跨行项单独加上，即可得到闭式答案。",
            "primary_topic": "基础实现与模拟",
        },
        "2248C": {
            "statement_brief": "长度 2n 的数组中每个值出现两次。每次选一个仍存在的值，删除它当前最左和最右出现位置之间的整段并获得区间长度平方分数，求最大总分。",
            "transformed_statement": "把题目先看成：最优操作可以规范化为删除原数组中的完整配对区间；于是整个过程等价于把数组划分成若干不相交块，每块要么是单点，要么由相同值两端包住。",
            "key_observations": [
                "若某个值的原始配对区间内部已经先删掉一段，把这次删除提前不会变差，因为大区间平方不小于拆开后的平方和。",
                "反复交换后，可以认为每次操作都删除一个完整原始区间；这些区间之间不相交，剩余位置作为单点块。",
                "设 dp[i] 为前 i 个位置的最大分数，最后一块要么是单点 i，要么是 a_i 第一次出现位置到 i 的整段。",
            ],
            "solution_brief": "关键观察：平方收益让“先删内部、再删外层”不优于直接删完整外层。把过程化为前缀划分 DP：dp[i]=max(dp[i-1]+1, dp[l-1]+(i-l+1)^2)，其中 l 是 a_i 的前一次出现位置。",
            "primary_topic": "动态规划与状态设计",
        },
        "2239B": {
            "statement_brief": "圆桌上每个人有权值和固定视野。决定哪些人收礼；收礼者因视野内未收礼人数得正分，未收礼者因视野内收礼人数扣分，求总幸福值最大值。",
            "transformed_statement": "把题目先看成：是否给某个人礼物的边际贡献可以独立计算；其它人的选择只通过视野内权值和进入这个边际值。",
            "key_observations": [
                "把某个人从不收礼改成收礼，会让他自己的贡献增加 2d·a_i。",
                "同时，他会影响左右各 d 个人的贡献，总共减少这些邻居权值之和。",
                "因此每个人的选择互不耦合：只要边际贡献为正就给礼物，否则不给。",
            ],
            "solution_brief": "关键观察：礼物选择可以拆成每个人独立的边际收益。对位置 i 计算 2d·a_i 减去左右 d 个邻居的权值和，只把正收益加进答案；环上滑动窗口即可线性处理。",
            "primary_topic": "构造与贪心",
        },
        "2226A": {
            "statement_brief": "每次可以删除一个按原下标递增、值也非降的子序列，代价为所删元素乘积。要求清空数组的最小总代价。",
            "transformed_statement": "把题目先看成：大于 1 的数不应互相合并；值为 1 的元素应尽量搭到后面的某个大数上，因为不会增加乘积代价。",
            "key_observations": [
                "两个都大于 1 的正整数相乘不小于二者之和，所以把它们放在同一次操作里不会更优。",
                "若若干个 1 能和后面的某个大于 1 的数一起作为非降子序列删除，代价仍只是那个大数。",
                "所有大于 1 的元素贡献其自身；若数组最后一个元素是 1，则至少有一批结尾的 1 只能单独删除，额外代价为 1。",
            ],
            "solution_brief": "关键观察：乘积代价下，大数分开删、1 尽量免费附着到后面的大数。答案为所有大于 1 元素之和，再根据最后一位是否为 1 额外加 1。",
            "primary_topic": "构造与贪心",
        },
        "2189C1": {
            "statement_brief": "简单版要求构造 1..n 的排列 p，使每个中间位置 i 都能在后缀中找到 j，满足 p_i = p_j 与 i 的异或。",
            "transformed_statement": "把题目先看成：强行让所有位置都找同一个见证 j=n；只要固定 p_n=1，其余中间位置就被迫成相邻偶奇对交换。",
            "key_observations": [
                "条件等价于 p_i 与 i 的异或等于 p_j；若统一令见证值 p_n=1，就需要 p_i=i 与 1 的异或。",
                "偶数 2k 与 1 异或得到 2k+1，奇数 2k+1 与 1 异或得到 2k，因此中间位置天然成对交换。",
                "剩下没有被中间位置占用的一个数放到 p_1；n 的奇偶只影响这个剩余数是谁。",
            ],
            "solution_brief": "关键观察：把所有约束都压到同一个后缀见证 p_n=1。然后按 (2,3)、(4,5) 这类相邻偶奇对交换填中间位置，首位放剩余数字即可。",
            "primary_topic": "构造与贪心",
        },
        "2187D": {
            "statement_brief": "给含问号的二进制串和常数 x、y。每种补全会生成数组 c 并得到 f 值，求所有可能 f 值之和。",
            "transformed_statement": "把题目先看成：虽然 f 是整条路径的和，但题解把它化成只依赖最终 c_n 的表达式；于是核心变为统计所有可达的 c_n。",
            "key_observations": [
                "对转移式做配方后，可以推出 f(r) 等于关于 c_n 的二次表达式，而不需要保存每个中间 c_i。",
                "c_n 对 y 的系数只会是 0 或 1，对 x 的系数可用状态集合维护。",
                "因此对前缀做可达性 DP：处理 0、1、? 三种字符时更新 x 系数和 y 系数，最后枚举可达 c_n 求对应 f 值之和。",
            ],
            "solution_brief": "关键观察：先代数化简，把整段生成数组的和压缩成最终值 c_n 的函数。再用 DP 统计所有补全能到达哪些 c_n，配合位集优化状态集合，最后把每个可达终值代回公式求和。",
            "primary_topic": "动态规划与状态设计",
        },
        "2183E": {
            "statement_brief": "给严格递增序列，其中 0 需要替换成 1..m 的数。要求相邻最小公倍数倒数之和加上首尾项至少为 1，计数所有合法替换。",
            "transformed_statement": "把题目先看成：题解先用不等式把总和上界压到 1/a_1；要达到至少 1，所有不等式必须同时取等。",
            "key_observations": [
                "当 x<y 时，gcd(x,y) 不超过 y-x，所以 1/lcm(x,y)=gcd(x,y)/(xy) 不超过 (y-x)/(xy)。",
                "前 n-1 项按这个上界会望远镜相消；首尾项还要求 a_1=1，最终总上界不超过 1。",
                "因此合法序列必须满足 a_1=1，且每一对相邻数都有 gcd(a_i,a_{i+1})=a_{i+1}-a_i；这等价于差值是前一个数的因子。",
            ],
            "solution_brief": "关键观察：原不等式实际上只能在一串等号条件下成立。把条件化成 a_1=1 且相邻差值整除前项后，预处理每个数可跳到的后继，再按位置做 DP 计数。",
            "primary_topic": "数论与同余",
        },
        "2140E2": {
            "statement_brief": "有 n 堆石子和若干可删除下标，双方轮流删除当前数组中的可删除下标，最后剩下一堆。Alice 最大化最后石子数，Bob 最小化；求所有初始配置的最终值总和。",
            "transformed_statement": "把题目先看成：对每个阈值 t，只判断最后剩余值是否至少为 t；每堆石子可压成一位 0/1，博弈只依赖这个掩码。",
            "key_observations": [
                "最终值 x 的总和可写成对所有阈值 t 的指示值求和：判断 x 是否至少为 t。",
                "固定 t 后，每堆只需区分是否不小于 t；原石子数变成一个长度 n 的二进制掩码。",
                "对每个掩码做普通极大极小 DP，得到 Alice 是否能保证最终位为 1；再按掩码中 1 的个数统计有多少真实配置对应它。",
            ],
            "solution_brief": "关键观察：把数值博弈转为阈值布尔博弈。先对所有二进制掩码预处理胜负，再枚举阈值 t，用 (t-1) 与 (m-t+1) 的幂统计每类掩码对应的配置数并累加。",
            "primary_topic": "博弈",
        },
        "2135D1": {
            "statement_brief": "交互题。隐藏一个文本编辑器行宽 W；你可以提交若干单词长度组成的文章，交互方返回显示所需行数或表示无法显示。简单版没有所有询问文章长度总和限制。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是通过构造文章长度来反推出隐藏行宽的交互题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2127G1": {
            "statement_brief": "交互题。隐藏排列 p 且没有固定点；先固定一个位置 k，之后每次提交一个排列 q，返回满足若干条件的有向边数量。要求恢复整个 p。",
            "transformed_statement": "把题目先看成：隐藏排列是一张每点出度为 1 的有向图；一次询问和一次“除 k 外反转”的询问相加，可以定位某个点的前驱落在哪个候选半区。",
            "key_observations": [
                "把边看成 i 指向 p_i，询问本质是在数有多少边在排列 q 中从左指向右，并忽略起点位于第 k 位的边。",
                "把目标点 i 放在第 k 位后，边 i 指向 p_i 永远不计；其它不相关边在原排列和反转排列中总共恰好计一次。",
                "唯一会改变总和的是指向 i 的那条边；根据两次询问和是 n-1 还是 n-2，就能判断前驱在哪个候选集合。",
                "选合适的 k 让可放置区域接近二分，每轮把候选前驱集合缩半，逐个点恢复其前驱即可得到排列。",
            ],
            "solution_brief": "关键观察：询问 q 和反转 q 的和会抵消绝大多数边，只留下“谁指向 i”所在半区的信息。对每个 i 二分它的前驱，最后由所有前驱关系还原隐藏排列。",
            "primary_topic": "交互",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2082B": {
            "statement_brief": "给整数 x，必须恰好做 n 次向下除以 2 和 m 次向上除以 2，操作顺序任意；求最终值的最小和最大可能值。",
            "transformed_statement": "把题目先看成：连续除以 2 只是在删二进制低位；最终值只可能是高位部分，或因为低位进位变成高位部分加一。",
            "key_observations": [
                "总共做 n+m 次操作后，x 的低 n+m 位被处理掉，高位部分保留下来。",
                "最大值应先做所有向下取整，再做向上取整，这样低位中只要能产生进位就尽量保留。",
                "最小值则反过来，先做所有向上取整，再做向下取整；同一种操作连续做到 x 变成 0 或 1 后可以停止模拟。",
            ],
            "solution_brief": "关键观察：操作顺序的极值有固定形态。最大值为先向下取整 n 次再向上取整 m 次，最小值为先向上取整 m 次再向下取整 n 次；因为 x 很快缩到 0/1，直接模拟即可。",
            "primary_topic": "数论与同余",
        },
        "2062D": {
            "statement_brief": "给树上每个点可选的初始值区间，可以对任意换根意义下的一棵子树整体加一，要求最终所有点相等并最小化这个相等值。",
            "transformed_statement": "把题目先看成：一旦各点初值确定，每条父子边的差值必须被修平；根所在连通块最终额外增加的次数只取决于父子差的正部分。",
            "key_observations": [
                "固定根为 1 和所有 a_i 后，修平边 (父亲,u) 至少需要 |a_u-a_父亲| 次有效操作。",
                "这些操作中会推高根侧最终值的，正好是所有 max(a_u-a_父亲,0) 的总和，所以目标变成选 a 最小化该表达式。",
                "对子节点值已定时，当前点取值不应低于孩子最大需求，也不应低于 l_u；若超过 r_u 则只能取 r_u，这给出自底向上的贪心。",
            ],
            "solution_brief": "关键观察：树操作可化为边差代价，最终值是 a_1 加上所有向下正差。后序处理每个点，把它的值选成区间内尽量覆盖孩子最大值的最小可行数，再累加父子正差得到答案。",
            "primary_topic": "树结构",
        },
        "2056E": {
            "statement_brief": "给一个两两不交或互相包含的线段集合 S，要求加入尽可能多的新线段后仍保持这个性质，并计数所有最大扩充方案。",
            "transformed_statement": "把题目先看成：这种线段族天然是一棵包含树；最大扩充就是把每个内部节点补成满二叉结构，计数则分解为每个节点孩子的合并方式。",
            "key_observations": [
                "先补上整段 [1,n] 和所有单点线段后，线段包含关系形成一棵有 n 个叶子的树。",
                "若某个节点有超过两个孩子，就可以把相邻孩子合并成一个新线段，从而继续增大集合；最大时每个内部节点必须恰有两个孩子。",
                "有 n 个叶子的满二叉树总节点数为 2n-1，所以最大大小固定；每个已有节点的孩子顺序独立，c 个孩子合并成二叉树有第 c-1 个卡特兰数种方式。",
            ],
            "solution_brief": "关键观察：好线段集合就是层级包含树，最大扩充等价于把它补成满二叉树。构建包含树后，对每个非叶节点乘上“把 c 个有序孩子二叉合并”的卡特兰数即可。",
            "primary_topic": "组合计数与概率",
        },
        "2048F": {
            "statement_brief": "给两行正整数 a、b。一次选择区间 [l,r]，令 x 为该区间 b 的最小值，并把区间内每个 a_i 变成向上除以 x；求把所有 a_i 变成 1 的最少操作次数。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是带区间最小值作为除数的批量缩小问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "数据结构",
        },
        "2030B": {
            "statement_brief": "构造长度为 n 的二进制串，使只含 0 的非空子序列数与至少含一个 1 的非空子序列数之差的绝对值尽量小。",
            "transformed_statement": "把题目先看成：所有非空子序列被这两类完全划分，总数是奇数，因此两类数量之差的绝对值至少为 1。",
            "key_observations": [
                "f+g 等于全部非空子序列数量，也就是 2^n-1，恒为奇数。",
                "两个整数的和为奇数时，它们的差也为奇数，所以 |f-g| 不可能为 0。",
                "只放一个 1 时，只含 0 的非空子序列有 2^{n-1}-1 个，含 1 的子序列有 2^{n-1} 个，差值正好为 1。",
            ],
            "solution_brief": "关键观察：最小可能差值的下界是 1，而一个 1 加其余全 0 正好达到下界。直接输出任意只含一个 1 的二进制串。",
            "primary_topic": "组合计数与概率",
        },
        "2013F1": {
            "statement_brief": "简单版中 u=v。树上两人轮流从当前点走到未被任何人访问过的相邻点，无法移动者输；要求判断 Bob 从指定单点路径位置出发时的胜者。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是树上双人不回访移动博弈的单起点版本。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "树结构",
        },
        "2183B": {
            "statement_brief": "反复选择当前数组中长度为 k 且 MEX 最大的窗口，并从该窗口删除任意一个元素；最终剩 k-1 个元素，最大化最终 MEX。",
            "transformed_statement": "把题目先看成：最终只剩 k-1 个数，所以最终 MEX 不可能超过 k-1；同时原数组缺失的最小数也永远不可能被创造出来。",
            "key_observations": [
                "任意长度 k 的窗口里，若只看 0..k-2 这 k-1 个值，要么有重复，要么有元素不在这个范围内。",
                "因此每个可选窗口中总存在一个对保留 0..k-2 完整性无用的元素，可以把它删掉。",
                "最终 MEX 的上界是原数组 MEX 与 k-1 的较小值；上述删除策略能保住所有小于这个上界的值。",
            ],
            "solution_brief": "关键观察：长度 k 的窗口一定有一个“无效”元素可删，因为 k 个位置装不下 k 个互不重复的 0..k-2。答案就是 min(MEX(a), k-1)。",
            "primary_topic": "构造与贪心",
        },
        "2178E": {
            "statement_brief": "交互题。隐藏数组由初始相同的两个数组经过“拆最大偶数”和“拼接同步复制”生成；可询问区间和，要求在 300 次内求最大元素。",
            "transformed_statement": "把题目先看成：最后一次关键操作可以视为拼接，拼接前的两半总和相等；找到分界后，最大值一定在较短的那一半。",
            "key_observations": [
                "拆分最大偶数不会改变数组总和，拼接后两个数组也仍保持相同总和。",
                "因此最终数组若来自一次拼接，可以用前缀和二分找到左右两半总和相等的分界。",
                "较短的一半经历的拆分次数更少，而拆分不会增大最大值，所以较短一半必含有全局最大值。",
                "递归进入较短一半；长度每次至少减半，每层用二分找分界，询问次数满足限制。",
            ],
            "solution_brief": "关键观察：等和拼接给出可查询的分界，拆分次数更少的一半保留最大值。每轮用区间和二分分界，然后递归到较短半边，直到长度为 1。",
            "primary_topic": "交互",
        },
        "2160A": {
            "statement_brief": "把给定多重集合划分成若干个多重集合，要求每一份的 MEX 相同；求所有合法划分中的最小公共 MEX。",
            "transformed_statement": "把题目先看成：设全集 MEX 为 m。大于 m 的元素不会影响任何一份是否含有 0..m-1，因此真正约束只在这些小值上。",
            "key_observations": [
                "全集中没有 m，所以任何一份都不可能含有 m，公共 MEX 不会超过 m 的结构限制。",
                "只要全集里有 0，就至少有一份含 0；为了各份 MEX 相同，所有份都必须含 0。",
                "同理可依次推出每一份都必须含 1、2、直到 m-1，因此公共 MEX 只能是 m。",
            ],
            "solution_brief": "关键观察：从 0 开始逐层强制。若某个小值存在，为了所有份的 MEX 一致，每一份都必须含它；一直推到全集 MEX 前，答案只能是 MEX(A)。",
            "primary_topic": "基础实现与模拟",
        },
        "2157E": {
            "statement_brief": "一组无人机能量中，若某个值出现超过 k 次，就把同值中除最早出现者外的无人机能量加一；重复直到所有值出现次数不超过 k，求操作轮数。",
            "transformed_statement": "把题目先看成：元素顺序不重要，可以排序并自行规定同值保留哪一个；对固定轮数，可以直接算每个元素会变成什么值。",
            "key_observations": [
                "排序后可先研究 k=1 的终态：从右往左看，每个元素最终停在不小于初值且尚未被占用的最小值。",
                "单个元素的值随轮数从 a_i 逐步加到终态 b_i，之后保持不变。",
                "一轮操作不会让任意值的出现次数上升；因此是否已经满足每个值最多 k 次关于轮数单调，可二分答案。",
            ],
            "solution_brief": "关键观察：把过程理解成每个元素沿着整数轴向右移动到自己的最终坑位。二分轮数，按排序后的终态计算该轮后的配置并检查最大重数是否不超过 k。",
            "primary_topic": "数据结构",
        },
        "2081A": {
            "statement_brief": "给一个二进制表示的整数 x。每次等概率选择向下除以 2 或向上除以 2，直到 x 变成 1；求期望操作次数。",
            "transformed_statement": "把题目先看成：删掉低位时，操作次数只可能是 n-1 或 n；差别在于最后一次处理低位时是否产生向高位的进位。",
            "key_observations": [
                "每次除以 2 相当于向右移一位；没有进位时，长度为 n 的数到 1 需要 n-1 步。",
                "向上取整可能把低位的 1 向更高位传递，若在第 n-1 次仍有进位，则会多做一步。",
                "设 f_i 为处理到第 i 个低位时仍有进位的概率，可按当前位是 0 还是 1 做一维递推。",
            ],
            "solution_brief": "关键观察：随机性只影响“最终是否多一轮”。从低位往高位递推进位概率，答案为 n-1 加上最高处理前仍有进位的概率。",
            "primary_topic": "组合计数与概率",
        },
        "2022D2": {
            "statement_brief": "困难版交互题要求用最少询问找出唯一冒名者；每次询问一个人是否认为另一个人是骑士。",
            "transformed_statement": "把题目先看成：询问结果是一张带 0/1 权的有向图；环上权值和的奇偶可以判断冒名者是否在这个环里。",
            "key_observations": [
                "若一个有向环不含冒名者，假话边数量为偶数；把冒名者插入环会改变这个奇偶性。",
                "这推广了 简单版的互问判定，也能证明少于 n 次询问无法区分某些身份分配。",
                "构造上仍可成对删除安全人，把规模降到 4 或 5；规模 5 时用三点环的奇偶判断先区分候选集合，再用互问收尾。",
            ],
            "solution_brief": "关键观察：把交互回答转成带奇偶信息的有向图。下界用入度/出度缺口和环奇偶构造不可区分身份；上界则成对缩小规模，并用 4/5 人的最优小策略收尾。",
            "primary_topic": "交互",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2228C1": {
            "statement_brief": "简单版中可用数字只有两个。给非负整数 a 和递增数字集合 d，求只由 d 中数字组成的非负整数 b，使 |a-b| 最小。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是限制十进制可用数字后的最近数问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "动态规划与状态设计",
        },
        "2190B2": {
            "statement_brief": "给括号串 s，要求对 s 的所有非空子序列计算分数并求和；分数是比原串字典序更好的最长合法括号子序列长度，不存在则为 0。",
            "transformed_statement": "把题目先看成：一个子序列若有正分，分数一定等于长度减 2；核心只剩计数哪些合法括号子序列内部含有模式 “)(”。",
            "key_observations": [
                "题解证明固定长度下，分数只可能是 0 或长度减 2。",
                "能得到长度减 2 的更好子序列，等价于原子序列本身合法，且存在形如 “)(” 后面还有 “(” 的三字符子序列；可放宽为含有 “)((” 作为子序列。",
                "于是问题变成计数合法括号子序列，同时记录当前余额、长度，以及模式 “)((” 已匹配到几位。",
            ],
            "solution_brief": "关键观察：正分子序列的贡献统一是长度减 2。用 DP 统计余额为 0 且已经包含 “)((” 模式的子序列数量和长度和，最后按长度减 2 累加即可。",
            "primary_topic": "动态规划与状态设计",
        },
        "2161A": {
            "statement_brief": "给初始分数、二类比赛门槛、单场最大可控变化和赛程串；一类赛总是计分，二类赛只有分数低于门槛才计分，求最多参加多少场计分赛。",
            "transformed_statement": "把题目先看成：一类赛必然计入，二类赛的价值在于分数是否已经被压到门槛以下；策略就是尽早把分数降到门槛减一。",
            "key_observations": [
                "一类赛无论当前分数如何都会计分，因此不会损失参赛次数。",
                "每场计分赛后可以把分数调到允许区间内任意值，所以若还没低于门槛，就应尽量下降。",
                "一旦分数达到门槛减一，之后所有二类赛也都会计分，总参赛数从这一刻起不再受赛程类型限制。",
            ],
            "solution_brief": "关键观察：目标不是最大化分数，而是尽快降到二类赛门槛下。顺序模拟赛程，计分时把分数尽量减小；低于门槛后剩余比赛全都可计入。",
            "primary_topic": "构造与贪心",
        },
        "2127G2": {
            "statement_brief": "困难版交互题。隐藏无固定点排列 p，固定位置 k 后，每次提交排列 q 并获得满足条件的有向边数量，要求用 10n 次询问内恢复 p。",
            "transformed_statement": "把题目先看成：排列是一张函数图。困难版先区分二环和长环，再分别用位置 k、循环平移和按位分组恢复边。",
            "key_observations": [
                "若整张图都是二环，把目标点放在 k 附近后，询问值能判断它的匹配点在左半还是右半，因此每条二环可二分找到。",
                "对一般环，比较一次排列和一次局部循环平移，只有穿过被移动块边界的两条边可能改变贡献。",
                "按平衡的二进制编号分组，多轮循环平移可以批量得到每个点前驱和后继的异或，从而判断是否属于二环。",
                "长环只需每个环再确定一条边，其余边可由已知异或关系沿环恢复；二环部分用前面的二分策略处理。",
            ],
            "solution_brief": "关键观察：查询结果可以看作函数图边的方向计数。先用按位分组和循环平移批量判断每个点是否在二环；二环用 k 位置二分配对，长环用已知前后继异或加少量二分恢复。",
            "primary_topic": "交互",
        },
        "2084A": {
            "statement_brief": "给 n，构造 1..n 的排列 p，使每个 i>=2 都满足 max(p_{i-1},p_i) 对 i 取余等于 i-1；无解则输出 -1。",
            "transformed_statement": "把题目先看成：奇数 n 可以把 n 放在第一位作为前两个位置的最大值，后续位置让相邻最大值自然等于 i-1；偶数 n 会因最大值 n 的位置产生奇偶矛盾。",
            "key_observations": [
                "当 n 为奇数时，排列 [n,1,2,...,n-1] 可行：i=2 时 n 对 2 取余为 1，i>=3 时相邻最大值就是 i-1。",
                "当 n 为偶数时，最大值 n 不可能放在首、次或末尾；若放在中间，会影响相邻两条约束。",
                "这两条约束中必有一个偶数模数 i 要满足 n mod i = i-1，但偶数对偶数取余不可能得到奇数 i-1。",
            ],
            "solution_brief": "关键观察：奇数 n 的顺序构造直接让每个相邻最大值命中目标余数；偶数 n 则由最大值 n 的相邻约束推出奇偶矛盾，因此无解。",
            "primary_topic": "构造与贪心",
        },
        "2062A": {
            "statement_brief": "给二进制串。一次可选择一个相邻字符交替的非空子序列并翻转其中字符，求把全串变成 0 的最少操作数。",
            "transformed_statement": "把题目先看成：一次操作最多能让 1 的数量减少 1；而每次单独翻转一个 1 总是合法。",
            "key_observations": [
                "被选子序列相邻字符必须交替，因此其中 1 和 0 的数量差最多为 1。",
                "翻转后，1 变 0、0 变 1，所以全串中 1 的数量一次最多减少 1。",
                "逐个选择每个为 1 的位置单独翻转，可以用恰好 1 的数量次完成。",
            ],
            "solution_brief": "关键观察：操作对 1 的数量最多净减少 1，这给出下界；单点翻转每个 1 达到这个下界。答案就是字符串中 1 的个数。",
            "primary_topic": "字符串",
        },
        "2061F1": {
            "statement_brief": "简单版中目标串只含 0 和 1。给初始二进制串 s，每次可交换相邻的两个同字符极大块；求最少操作使 s 匹配目标串 t，或判断无解。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是按同字符块交换来重排二进制串的最少操作问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "字符串",
        },
        "2048I1": {
            "statement_brief": "简单版给只含 L/R 的字符串 s，需要构造一个非负数组 a，使每个 L 位置等于其左侧不同值个数，每个 R 位置等于其右侧不同值个数；无解则报告。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是按左右不同值计数反向构造数组的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2030A": {
            "statement_brief": "可以任意重排数组 a。定义前缀最小值数组 b 和前缀最大值数组 c，分数为所有 c_i-b_i 之和；求最大分数。",
            "transformed_statement": "把题目先看成：每一项 c_i-b_i 都不可能超过全局最大值减全局最小值；从第二位开始让每一项都达到这个上界即可最优。",
            "key_observations": [
                "任意前缀的最大值不超过全局最大值，最小值不小于全局最小值，所以单项差值有统一上界。",
                "第一项总是 c_1=b_1，贡献为 0。",
                "把全局最大值放第一位、全局最小值放第二位后，从第二个前缀开始每项差值都达到全局差。",
            ],
            "solution_brief": "关键观察：每个非首项贡献最多为“全局最大值减全局最小值”，且这个上界可以通过先放最大、再放最小同时达到。答案是该差值乘以 n-1。",
            "primary_topic": "构造与贪心",
        },
        "2205G": {
            "statement_brief": "计数有序三元组 (i,j,k)，满足 0<=i,j,k<=m，且存在整数 x,y 使 (i 异或 j)x+(j 异或 k)y=n。",
            "transformed_statement": "把题目先看成：线性方程有整数解当且仅当两个系数的最大公约数整除 n；随后把对最大公约数的条件用莫比乌斯反演转成倍数计数。",
            "key_observations": [
                "由裴蜀定理，条件等价于 gcd(i⊕j,j⊕k) 是 n 的因子。",
                "枚举公因子后，用莫比乌斯反演把 gcd 恰等于某值改成统计 T 同时整除 i⊕j 和 j⊕k 的三元组数。",
                "固定 T 和 j 后，i、k 的候选可写成 dT⊕j；满足不超过 m 的 j 会形成少量二进制区间。",
                "用字典树或树状数组维护这些区间交集，就能批量求出所有 T 的贡献。",
            ],
            "solution_brief": "关键观察：先用裴蜀定理把“存在 x,y”变成 gcd 整除 n，再用莫比乌斯反演把 gcd 条件降为倍数条件。剩下要高效统计 dT⊕j<=m 的区间交集，题解用数据结构维护。",
            "primary_topic": "数论与同余",
        },
        "2205F": {
            "statement_brief": "在 n×m 网格道路中选择可重建边，要求每个路口相邻的重建边数为偶数，并满足部分边不可选；目标最大化题目定义的交替加减权值美观度。",
            "transformed_statement": "把题目先看成：所有偶度边集可以由每个小方格作为基向量组合出来；不可选边会强制它两侧的小方格基状态相同。",
            "key_observations": [
                "没有限制时，任意一组小方格的边界异或起来都会让每个网格点度数为偶数；反过来任意合法偶度边集也能分解成这些小方格基。",
                "一条不可重建边若位于两个小方格之间，就要求这两个方格是否被选择的状态相同；边界外侧可视为固定为不选的虚拟方格。",
                "用并查集维护这些相等约束后，每个连通块的总权值若为正就选择，否则不选择。",
            ],
            "solution_brief": "关键观察：把合法重建方案从“选边”改写成“选小方格基”。不可选边只是在相邻基之间加相等约束；并查集合并后，每个自由块独立取正贡献即可。",
            "primary_topic": "图论与网络流",
        },
        "2146A": {
            "statement_brief": "给非降数组，要求选一个最长子序列，使子序列中每种出现的值出现次数完全相同。",
            "transformed_statement": "把题目先看成：先假设每个保留值都保留 x 次；出现次数不足 x 的值不能保留，出现次数至少 x 的值都可贡献 x 个。",
            "key_observations": [
                "固定公共出现次数 x 后，最优长度是 x 乘以“原数组中出现次数至少 x 的不同值个数”。",
                "x 的范围只有 0..n，可以直接枚举。",
                "若把各值出现次数降序排列，也可等价地枚举第 i 大频次，答案为 max(i·c_i)。",
            ],
            "solution_brief": "关键观察：平衡子序列只需要决定公共保留次数 x。统计每个值的频次后枚举 x，能保留的值贡献 x 个，取最大长度即可。",
            "primary_topic": "基础实现与模拟",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2129D": {
            "statement_brief": "给一个可能含未知项的染色得分序列，要求计数有多少排列按“依次染黑 p_i，并给最近黑格加分”的过程能产生它。",
            "transformed_statement": "把题目先看成：第一个染黑的位置会把左右两侧完全分开；之后每段内部递归处理，只需额外记录段外左右端点会被加几次分。",
            "key_observations": [
                "枚举当前区间里第一个被染黑的位置后，左区间和右区间互不影响，只通过靠近哪侧端点给区间外端点贡献分数。",
                "因此可做区间 DP：状态记录 [l,r] 内部方案数，以及会给 l-1 和 r+1 各额外加多少分。",
                "某个格子被左侧格子吸引并给它加分的次数呈倍增距离约束，所以单点得分上界只有对数级，状态维度可控。",
            ],
            "solution_brief": "关键观察：最近黑格规则让“当前段第一个染黑点”成为递归分割点。用区间 DP 合并左右段，并用对数级的边界加分维度限制复杂度。",
            "primary_topic": "动态规划与状态设计",
        },
        "2109F": {
            "statement_brief": "两名角色在带颜色和权值的 n×n 网格中分别从左上、左下走到出口，路径代价为经过格子最大值。可给黑格加值，要求不改变上方角色最优代价并最大化下方角色最优代价。",
            "transformed_statement": "把题目先看成：二分下方角色能否被迫达到代价 x；可行性等价于能否用可加值黑格和边界筑起一条隔离出口的“墙”，同时保留上方角色的一条原最优通路。",
            "key_observations": [
                "先求上方角色原本的最小最大值路径代价，作为后续不能破坏的基准。",
                "若目标 x 不超过这个基准，则无需额外担心上方路径；若 x 更大，就必须避开某条仍能达到基准的通路。",
                "阻断下方角色到出口可转化为在网格对偶意义上建连通墙，黑格权值补到 x 的花费作为点权，白格不足则不可用。",
                "题解用多源搜索标出必须保留的上方超路径区域，再在六种边界墙形态上跑最小代价连通，配合二分答案。",
            ],
            "solution_brief": "关键观察：最大化下方路径代价就是筑一条达到阈值的隔离墙。二分阈值，先保护上方角色的原最优通路，再用带点权最短路检查是否能在预算内把黑格补成阻断墙。",
            "primary_topic": "图论与网络流",
        },
        "2228E1": {
            "statement_brief": "简单版只有一次查询且操作固定。给含 -1 的数组片段和总和 m，要求对所有非负补全 c，求前缀和平方和 f(c) 的总和。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是带固定值和总和约束的组合求和问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
        "2207F": {
            "statement_brief": "网格卡牌游戏中，每张牌有等级和颜色，提示会高亮同等级或同颜色的剩余牌，玩家总打出最左高亮牌。要求合法打完整副牌，并最小化提示类型变化次数。",
            "transformed_statement": "把题目先看成：提示序列可压缩掉相邻重复。最优序列中，等级提示可假设按等级递增，且一次等级提示会打出该等级所有剩余牌。",
            "key_observations": [
                "如果某个颜色提示会打出较低等级牌，它可以提前到对应等级提示前，不会破坏合法性。",
                "通过交换相邻等级提示，可把所有等级提示整理为递增顺序。",
                "在这个规范形态下，真正需要决策的是哪些等级用等级提示，哪些区间靠颜色提示穿过。",
                "设 DP 记录处理到某个等级时最后是否使用等级提示；转移枚举上一段颜色提示造成的变化次数。",
            ],
            "solution_brief": "关键观察：先把任意最优策略规范化，让等级提示递增并清空对应等级。之后问题只剩在等级轴上做 DP：选择某些等级直接提示，其余靠颜色提示连接，计算最少提示变化。",
            "primary_topic": "动态规划与状态设计",
        },
        "2183I2": {
            "statement_brief": "困难版给一个二进制数组，需要通过若干翻转操作构造满足要求的答案；规模很大，需要利用 1 的数量很少这一性质。",
            "transformed_statement": "把题目先看成：先把 1 尽量配对消掉，剩下极少数 1 后再用小规模状态 DP 补齐构造。",
            "key_observations": [
                "题解先给出若干贪心配对优化，包括从左右两个方向尝试，保证剩余的 1 不会太多。",
                "当剩余 1 的数量被压到常数级后，可以把它们的位置压成掩码。",
                "小掩码上的可达性和操作选择可预处理，最后把预处理结果映射回原数组位置。",
            ],
            "solution_brief": "关键观察：大规模部分不用完整搜索，先用配对操作把 1 的数量压到很小；剩余局面用掩码 DP 还原操作序列，从而兼顾构造正确性和复杂度。",
            "primary_topic": "动态规划与状态设计",
        },
        "2164F1": {
            "statement_brief": "简单版给一棵以 1 为根的树和数组 a，计数排列 p，使每个点 u 的祖先中恰有 a_u 个点的排列值小于 p_u。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是树上祖先相对排名约束下的排列计数问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "树结构",
        },
        "2129F1": {
            "statement_brief": "简单版交互题。隐藏排列 p，可询问一组位置或一组值对应的前若干大元素；查询次数有限，要求恢复整个排列。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是利用“前若干大值/位置”反馈恢复隐藏排列的交互题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2124F1": {
            "statement_brief": "简单版从空数组开始，每次追加某个 1..s 的循环移位。给若干位置不等于某值的限制，计数长度恰为 n 的可构造数组。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是把数组分解为若干循环排列块，并满足位置禁值限制的计数问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
        "2048D": {
            "statement_brief": "给参赛者分数和题目难度。对每个组大小 k，需要选若干题分成若干场比赛，使 Kevin 的总排名和最小。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是按比赛大小分组题目、最小化指定参赛者排名和的排序/分组问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2020E": {
            "statement_brief": "每个 a_i 独立按给定概率加入多重集合 S，令 f(S) 为所有选中数的异或，求 f(S)^2 的期望。",
            "transformed_statement": "把题目先看成：平方可以拆成二进制位对的贡献；只要求出最终异或值中每一对二进制位同时为 1 的概率。",
            "key_observations": [
                "若最终异或的第 i 位为 b_i，则 f(S)^2 等于所有 b_i b_j 乘以 2^{i+j} 的和。",
                "固定一对位 i、j 时，状态只有四种：这两位当前异或结果分别为 0/1。",
                "依次考虑每个元素是否被选中，用其对应两位翻转当前状态，就能维护四种状态的概率。",
            ],
            "solution_brief": "关键观察：不要直接处理整个异或值的分布，只处理二进制位对。对每对位做四状态概率 DP，最后把同时为 1 的概率按 2^{i+j} 加权求和。",
            "primary_topic": "组合计数与概率",
        },
        "2013E": {
            "statement_brief": "可以任意重排正整数数组，要求最小化所有前缀最大公约数之和。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是通过排列顺序控制前缀最大公约数下降速度的数论贪心/DP 问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "数论与同余",
        },
        "2249B": {
            "statement_brief": "给 n 和数组 a。对排列 p 的每个切口，取左右两侧最大值的较小者得到 v_i；要求计数满足 v_i=a_i 的排列数。",
            "transformed_statement": "把题目先看成：最大值 n 所在位置把所有切口分成左右两边；左侧 a 必须非降，右侧 a 必须非升。",
            "key_observations": [
                "任何切口的较小侧最大值都不可能是 n，因此 a 中出现 n 直接无解。",
                "枚举 n 的位置后，它左边的切口值等于左前缀最大值，必须非降；右边等于右后缀最大值，必须非升。",
                "固定合法分界后，把左侧序列和右侧反转序列合并成一个非降序列；每个值第一次出现时被迫放该值，之后出现时可选任意尚未使用且更小的值。",
            ],
            "solution_brief": "关键观察：n 的位置是唯一分界。验证左非降、右非升后，合并两侧需求序列；首次出现的最大值位置强制，重复出现提供“未用小值”的选择数，乘起来并对所有合法分界求和。",
            "primary_topic": "组合计数与概率",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2216B": {
            "statement_brief": "给 T、H、U 三种二维拼块数量，允许旋转，求能把全部拼块放进 n×3 网格的最小 n。",
            "transformed_statement": "把题目先看成：先按单块占用高度累加，再用几种固定组合节省高度。",
            "key_observations": [
                "T 和 U 组合可比单独放置少用 2 行，T 和 H 组合可少用 1 行。",
                "一个 H 可以从两个方向插入，因此多余 T 与 H 的配合有上限。",
                "若 T 远多于 U 和 H 能吸收的数量，就进入多余 T 的公式；否则按 T/U 配对节省行数。",
            ],
            "solution_brief": "关键观察：这题不是搜索摆放，而是套固定拼块组合的节省公式。比较 c_T 与 c_U+2c_H；若 T 过多用 2c_T+3c_H+2c_U+1，否则用 2c_T+3c_H+3c_U-min(c_T,c_U)。",
            "primary_topic": "构造与贪心",
        },
        "2152B": {
            "statement_brief": "在 (n+1)×(n+1) 网格上追逃：逃跑者每回合可四方向或停留，追击者每回合可八方向或停留。双方最优，求逃跑者被抓前能撑多久，或判断无限。",
            "transformed_statement": "把题目先看成：二维追逃可以拆成行、列两个一维问题；逃跑者沿某个轴跑向边界，追击者用八方向移动同时缩小两个坐标差。",
            "key_observations": [
                "若逃跑者在追击者上方，他至少能跑到上边界前不被同一行抓住；下方、左方、右方同理。",
                "追击者八方向移动时，每回合可以同时让行差和列差都不增，因此逃跑者无法超过这些边界距离上界。",
                "下界和上界重合，答案就是四个可逃方向对应时间中的最大值；若某个方向永远无法被逼近则输出无限。",
            ],
            "solution_brief": "关键观察：把网格追逃拆成两个坐标轴的边界时间。逃跑者选择最能拖延的一侧边界，追击者每步同时压缩两轴差距；计算行、列方向的最大可拖延时间即可。",
            "primary_topic": "博弈",
        },
        "2130A": {
            "statement_brief": "给一个非负整数多重集合。每次删除一个子集并把该子集的元素和或 MEX 加到分数，求最大总分。",
            "transformed_statement": "把题目先看成：除单个 0 外，用 MEX 操作不会比把元素按和计分更赚。",
            "key_observations": [
                "若用 MEX 操作的子集含重复数或含大于 MEX 的数，删掉这些多余元素后不会降低 MEX，剩余元素可另按和计分。",
                "对形如 {0,1,...,x} 的集合，只有 x=0 或 x=1 时 MEX 才可能优于最大元素。",
                "{0,1} 的 MEX 等于单独对 {0} 取 MEX 再把 {1} 按和计分，因此真正额外收益只来自每个 0。",
            ],
            "solution_brief": "关键观察：每个非零数直接按和计分最优，每个 0 单独取 MEX 能多拿 1 分。答案等于数组总和加上 0 的个数。",
            "primary_topic": "构造与贪心",
        },
        "2089B1": {
            "statement_brief": "简单版没有预先减一修改。给环形数组 a、b，每轮先逐点抵消 min(a_i,b_i)，再把剩余 a 右移一格；求 a 全为 0 的最少轮数。",
            "transformed_statement": "把题目先看成：把环复制成链后，a_i 的剩余量会沿右移方向寻找后面的 b 容量；消失时间就是对应前缀差第一次降回当前高度的位置。",
            "key_observations": [
                "把每个 a_i 看成左括号、b_i 看成右括号，抵消和右移过程等价于左括号不断向后寻找匹配右括号。",
                "令前缀差 c_i=sum(a_j-b_j)。对位置 i，最早清空时间是后面第一个 c_p<=c_i 的位置距离。",
                "所有 a_i 都清空需要等待这些距离的最大值；可在复制链上用单调栈求每个下一次不大于位置。",
            ],
            "solution_brief": "关键观察：环上流动可转成括号匹配。复制一倍数组，维护 a-b 的前缀差；每个位置找右侧第一个前缀差不大于它的位置，最大距离就是答案。",
            "primary_topic": "数据结构",
        },
        "2018D": {
            "statement_brief": "从数组中选若干不相邻元素染红，分数为红色元素最大值、最小值和个数之和，求最大分数。",
            "transformed_statement": "把题目先看成：最优解一定包含全局最大值；枚举当前允许的最小值后，只能选择值在 [最小值,最大值] 内的位置，这些位置形成若干连续块。",
            "key_observations": [
                "若最优解不含全局最大值，把某个最大值加入，最多删掉相邻两个已选点，分数不会变差。",
                "从大到小枚举最小值 l，逐步加入值不小于 l 的位置；可选位置形成若干连通块。",
                "长度为 s 的连续块最多选 ceil(s/2) 个不相邻位置。",
                "还要保证至少选到一个全局最大值；每个块维护最大值是否能出现在最大独立集的奇偶位置中。",
            ],
            "solution_brief": "关键观察：固定最小红值后，问题变成若干连续块上取最多不相邻点。按值降序加入位置，用并查集维护块大小和是否能保留最大值，枚举过程中更新最优分数。",
            "primary_topic": "数据结构",
        },
        "2140E1": {
            "statement_brief": "简单版中每堆石子数只可能为 1 或 2。双方轮流删除当前编号属于可删集合的石堆，最后剩一堆；求所有初始配置的最终石子数总和。",
            "transformed_statement": "把题目先看成：每个配置就是一个二进制掩码，删除石堆会把掩码压缩；双方只是在这个掩码游戏上做极大极小选择。",
            "key_observations": [
                "m=1 时只有一种配置，答案直接确定；m=2 时石子数可用 0/1 表示。",
                "状态由当前长度、掩码和轮到谁操作组成，转移枚举所有当前可删位置并删除对应位。",
                "轮到 Alice 取后继最大结果，轮到 Bob 取后继最小结果；对所有初始掩码累加终态值。",
            ],
            "solution_brief": "关键观察：数值范围只有 1/2，整个游戏可以压成删位掩码 DP。枚举当前可删编号转移，按玩家取最大或最小，最后遍历所有初始掩码求和。",
            "primary_topic": "博弈",
        },
        "2063F2": {
            "statement_brief": "困难版逐步给出平衡括号串中的好括号对；每次加入后，计数与当前已知好括号对相容的平衡括号结构数量。",
            "transformed_statement": "把题目先看成：好括号对会把括号串切成若干最小平衡块；一次新增只会拆开其中一个块，其他块的卡特兰因子不变。",
            "key_observations": [
                "栈匹配中同时弹出的一对括号就是好括号对；其内部和外部都必须各自平衡。",
                "每个长度为 2t 的未知最小块可独立贡献第 t 个卡特兰数。",
                "困难版需要动态维护块的切分关系；新增好括号对时，只更新被它分裂的局部结构和答案因子。",
                "题解用可按下标切分、查询内外子序列的动态序列结构维护这些块。",
            ],
            "solution_brief": "关键观察：答案是若干最小平衡块的卡特兰数乘积。新增一对好括号只会局部拆块，因此维护动态括号块结构，删除旧因子、乘上新因子即可。",
            "primary_topic": "数据结构",
        },
        "2063F1": {
            "statement_brief": "简单版逐步给出平衡括号串中的好括号对；每次加入后，计数与当前信息相容的平衡括号序列数量。",
            "transformed_statement": "把题目先看成：已知好括号对会把原串切成若干必须平衡的最小子序列，各块内部可独立选择任意平衡括号结构。",
            "key_observations": [
                "好括号对正是普通栈匹配算法中一起弹出的括号对。",
                "若一对括号已知为好括号对，那么它的内部和外部都必须平衡，否则这对括号不会被一起弹出。",
                "把已知对作为切割边，重跑改造后的栈过程即可得到若干最小平衡块。",
                "长度为 2t 的块有第 t 个卡特兰数种填法，所有块独立相乘。",
            ],
            "solution_brief": "关键观察：不要枚举整棵括号树，只要把已知好括号对切出的最小平衡块找出来。简单版每次更新后线性重跑栈过程，按块长乘卡特兰数。",
            "primary_topic": "组合计数与概率",
        },
        "2061A": {
            "statement_brief": "可以重排数组。按顺序把每个数加到累计和 s；若 s 为偶数得 1 分，并不断除以 2 直到 s 变奇数。求最多得分。",
            "transformed_statement": "把题目先看成：第一次操作后 s 总是奇数；之后只有加入奇数才能让 s 变偶并得分。",
            "key_observations": [
                "若第一位放偶数，第一次可以得分，随后 s 被除到奇数。",
                "从第二步开始，奇数加奇数才会变偶，因此每个奇数都能贡献 1 分，偶数不能。",
                "若没有偶数，第一步放奇数不得分，剩下奇数各贡献一次。",
            ],
            "solution_brief": "关键观察：有偶数时先放一个偶数拿首分，之后所有奇数都能拿分，答案为奇数个数加一；全是奇数时第一步无法得分，答案为奇数个数减一。",
            "primary_topic": "构造与贪心",
        },
        "2049E": {
            "statement_brief": "交互题。隐藏长度为 2 的幂的二进制数组，恰有一个 1；隐藏阈值 k 会让长度至少 k 的区间和查询结果取反。要求在 33 次内找出 k。",
            "transformed_statement": "把题目先看成：先定位唯一的 1 在哪半边，再用包含或避开这个 1 的区间，把查询结果变成关于 k 的单调判定。",
            "key_observations": [
                "查询前两个四分之一区间：若结果不同，唯一的 1 在左半；若相同，则在右半。",
                "再查询包含该半边的长度 n/2 区间，可判断 k 是否小于 n/2。",
                "之后根据 k 位于小半区还是大半区，选择包含 1 或不包含 1 的区间做二分，查询结果对猜测 k' 单调。",
            ],
            "solution_brief": "关键观察：设备只在区间长度达到 k 时翻转。先用少量查询确定 1 的半边和 k 的半区，再构造单调查询二分 k，总询问数不超过限制。",
            "primary_topic": "交互",
        },
        "2048C": {
            "statement_brief": "给一个以 1 开头的二进制串，选择两个非空子串，允许重叠，使它们按二进制数异或后的值最大，并输出两个子串区间。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是二进制子串异或最大化的区间选择问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "字符串",
        },
        "2209E": {
            "statement_brief": "定义 f(t) 为字符串 t 能被拆成的最多段数，要求每段都是 t 的非空前缀。给定字符串 s，回答每个区间 [l,r] 中所有前缀子串 s[l..j] 的 f 值之和。",
            "transformed_statement": "把题目先看成：最优拆分由前后缀相同的真前缀链决定；反复去掉最短的这种真前缀，直到剩下无此结构的串，就得到唯一最优拆分。",
            "key_observations": [
                "若一个串存在前后缀相同的真前缀，则最短的这种前缀本身一定不再有同类结构。",
                "任意最优拆分中的每一段都可以继续拆到没有同类结构，因此最优拆分等价于拆成这种不可再拆的前缀。",
                "这个拆分唯一，最后一段必须是当前串的最短真前缀；所以不断裁掉它即可确定答案。",
            ],
            "solution_brief": "关键观察：前后缀相同前缀的嵌套关系决定唯一最优拆分。用前缀函数求每个前缀的最短真前缀长度，再递推 f_i=f_{i-b_i}+1；每个询问独立线性处理。",
            "primary_topic": "字符串",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2205E": {
            "statement_brief": "给目标数组 T，计数有多少原数组 S 能通过“把 S 划分成若干连续段并分别翻转”后得到 T。",
            "transformed_statement": "把题目先看成：为了避免同一个 S 被多种切分重复计数，可以规定每一段都不能存在相同的真前后缀。",
            "key_observations": [
                "设 dp[i] 表示能生成 T 的前 i 项的不同原数组数量，转移枚举最后一段的起点。",
                "如果某段有相同真前后缀，就可以把切分边界移动，导致同一个 S 被重复表示。",
                "因此只统计没有相同真前后缀的段；对每个右端点用前缀函数判断哪些左端点合法。",
            ],
            "solution_brief": "关键观察：把每个原数组唯一归约到“所有翻转段都无相同真前后缀”的切分。随后做前缀 DP，枚举最后一段，并用类 KMP 的预处理判段是否合法。",
            "primary_topic": "字符串",
        },
        "2176F": {
            "statement_brief": "给数组 a 和指数 k，要求对所有下标对 (i,j) 计算两数乘积的不同质因子个数的 k 次方之和。",
            "transformed_statement": "把题目先看成：乘积的不同质因子数等于两个数各自的不同质因子数之和，再减去二者最大公约数中的不同质因子数。",
            "key_observations": [
                "在本题范围内，单个数的不同质因子个数很小，可以作为状态维度。",
                "先按倍数统计：有多少数组元素被 g 整除，且自身不同质因子个数为某个值。",
                "再从大到小枚举 g，像精确最大公约数计数一样扣掉更大倍数的贡献，得到 gcd 恰为 g 的配对数。",
            ],
            "solution_brief": "关键观察：先把乘积质因子个数拆成两端贡献减公共贡献。按 g 和两端质因子个数分组计数，扣除更大 gcd 后，累加 (两端个数和-g 的个数)^k。",
            "primary_topic": "数论与同余",
        },
        "2059D": {
            "statement_brief": "两张同点数无向连通图中各有一个棋子。每步两个棋子同时沿各自图走到邻点，代价为两个新点编号差的绝对值；要求无限步总代价最小，若无法有限则输出 -1。",
            "transformed_statement": "把题目先看成：若想无限总代价有限，最终必须进入零代价循环，也就是两个棋子在同编号点，且两图存在同一条可来回走的公共边。",
            "key_observations": [
                "有限总成本意味着后面每一步代价都必须为 0，所以两个棋子最终要同步停在同编号状态上。",
                "还必须能沿两张图中的同一条边来回走，才能产生无限长的零代价后缀。",
                "先标出所有满足该公共边条件的好点，再在状态为 (v1,v2) 的乘积图上求最小代价到达任意 (v,v)。",
            ],
            "solution_brief": "关键观察：无限过程只需付到达零代价循环前的成本。构造两图乘积状态图，边权为新编号差；跑最短路到任意同编号好状态，取最小值，否则无解。",
            "primary_topic": "图论与网络流",
        },
        "2029C": {
            "statement_brief": "给若干场比赛表现值，必须跳过一个非空连续区间；其余比赛按当前分数与表现值比较执行 +1、0、-1，求最终分数最大值。",
            "transformed_statement": "把题目先看成：跳过一段后，前缀处理出的分数需要能接上后缀达到目标分数所需的最低入口。",
            "key_observations": [
                "可二分最终目标分数 k；正向模拟不跳过时的前缀最高可达分数。",
                "反向计算 g_i：若从第 i 场前至少有多少分，才能在不跳过 i..n 的情况下最终达到 k。",
                "枚举跳过区间右端点，用前缀最大值判断是否存在左端点，使跳过前分数不低于跳过后缀所需入口。",
                "也可直接用三状态 DP 表示跳过前、跳过中、跳过后。",
            ],
            "solution_brief": "关键观察：删区间不是模拟所有区间，而是把它变成前缀能力和后缀需求的拼接判定。线性 DP 三状态即可求最大最终分数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2019A": {
            "statement_brief": "从数组中选若干不相邻元素，分数为所选元素最大值加所选个数，求最大分数。",
            "transformed_statement": "把题目先看成：所选个数最多是向上取整的 n/2；若能在最大独立集大小下选到全局最大值，就得到最高分，否则少选一个也可保留最大值。",
            "key_observations": [
                "路径上最多能选上取整的 n/2 个不相邻位置。",
                "若 n 为奇数，唯一的最大大小方案选的是所有奇数位；只有最大值出现在奇数位时能同时达到最大个数和最大值。",
                "若 n 为偶数，总能选择某种最大大小方案覆盖任意一个指定位置。",
            ],
            "solution_brief": "关键观察：答案只在“最大值加上取整的 n/2”和少 1 之间。偶数长度一定能取最高；奇数长度只有当某个最大值在奇数位时取最高，否则为最大值加下取整的 n/2。",
            "primary_topic": "构造与贪心",
        },
        "2232C2": {
            "statement_brief": "困难版座位安排题。固定顺序来人，每人是内向、外向或中间型；桌数、每桌座位数给定，要求按性格约束尽量安排更多人入座。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是带顺序和桌子状态约束的最大可安排人数问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "动态规划与状态设计",
        },
        "2232C1": {
            "statement_brief": "简单版座位安排题。固定顺序来人，每人是内向、外向或中间型；桌数、每桌座位数较小，要求按性格约束尽量安排更多人入座。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是带顺序和桌子状态约束的最大可安排人数问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "动态规划与状态设计",
        },
        "2228B": {
            "statement_brief": "两人在环上追逃：逃跑者每秒可停或走一步但总共最多走 k 次，追击者看完后也可停或走一步。双方最优，求追上所需秒数。",
            "transformed_statement": "把题目先看成：状态只需要环上最短距离；逃跑者每次有效移动最多让追击时间多一秒，追击者每秒把距离缩短一格。",
            "key_observations": [
                "当 n<=3 时，追击者总能一秒追上。",
                "当 n>=4 时，逃跑者在距离为 1 时仍能沿环另一侧拉开距离，因此每次可用移动都能多拖一秒。",
                "初始最短环距需要这么多秒追上，再加上逃跑者最多 k 次有效移动带来的延迟。",
            ],
            "solution_brief": "关键观察：复杂策略退化成最短环距的变化。n<=3 答案为 1；否则答案为初始最短距离加 k。",
            "primary_topic": "博弈",
        },
        "2194F1": {
            "statement_brief": "简单版给一棵带点权的树和至多 4 个目标异或值集合。计数删边集合，使删边后每个连通块的点权异或都属于目标集合。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是树上删边后按连通块异或值计数的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "树结构",
        },
        "2183G": {
            "statement_brief": "交互题。数轴上每条蛇速度为 0、1、2 中之一，位置已知。最多给三条左右移动指令，根据幸存蛇位置恢复所有速度，若无法唯一确定则输出 -1。",
            "transformed_statement": "把题目先看成：固定询问 L、LR、R 三种指令；幸存集合和回到原位的对应关系能先确定大部分速度，剩余只需处理少数相邻碰撞模式。",
            "key_observations": [
                "执行 L 后再执行 R 不会改变幸存蛇的相对顺序，且 LR 后幸存蛇回到初始位置，因此 L 与 LR 的幸存数量相同。",
                "用幸存蛇的初始位置对应关系，可以推出所有在 L 后仍存活的蛇的速度。",
                "死于 L 的蛇只会落入少数局部模式；其中 0,1,0 与 0,2,0 无法区分，这是必须输出 -1 的唯一障碍。",
            ],
            "solution_brief": "关键观察：三条固定指令已经足够提供碰撞指纹。先由 L 和 LR 的对应关系确定幸存者，再用 R 查询和局部相邻模式推出死者速度；若出现不可区分三元模式则无解。",
            "primary_topic": "交互",
        },
        "2152D": {
            "statement_brief": "区间游戏中，一方每次把某个数向下除以 2，另一方每次把某个数加 1，直到全为 1；多次询问要求双方最优时前者操作次数。",
            "transformed_statement": "把题目先看成：单个数在对手干扰下等价于反复执行向下取整的 (x+1)/2，再按数是否为 2 的幂或 2 的幂加一分类。",
            "key_observations": [
                "单个数的基础贡献是二进制最高位位置。",
                "若数正好是 2 的幂，不会产生额外代价；若是 2 的幂加一，它是否额外花一步取决于同类数量的配对。",
                "其它数必然额外贡献一步。",
                "区间询问只需维护基础贡献和、幂加一类数量、其它类数量三个前缀统计。",
            ],
            "solution_brief": "关键观察：每个数的博弈贡献可静态分类。区间答案为基础贡献和，加上“2 的幂加一”数量的一半向下取整，再加其它类数量。",
            "primary_topic": "博弈",
        },
        "2048I2": {
            "statement_brief": "困难版给只含 L/R 的字符串 s，需要计数非负数组 a，使每个 L 位置等于其左侧不同值个数，每个 R 位置等于其右侧不同值个数。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是按左右不同值计数约束来统计数组数量的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "代数、矩阵与多项式",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2048B": {
            "statement_brief": "给定 n 和 k，要求构造一个长度为 n 的排列，使所有长度为 k 的连续子数组最小值之和尽量小。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是排列构造题，目标是让小数尽量覆盖更多长度为 k 的窗口。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2046E1": {
            "statement_brief": "有若干参赛者分属 2 个城市，每人有力量、专题和智慧。要构造不超过 5n 道专题各不相同的题，使 1 号城市任意人解题数都严格多于 2 号城市任意人；无解则输出 -1。",
            "transformed_statement": "把题目先看成：每个城市对应一个力量区间；区间不重叠时用普通难度题拉开差距，区间重叠时只能靠强组成员的专属专题补差。",
            "key_observations": [
                "若前一城市的最低力量不大于后面隔一组城市的最高力量，中间至少需要差 2 题，但一个专题最多只能补 1 题，直接无解。",
                "相邻两组力量区间不重叠时，放两道难度位于弱组最高力量和强组最低力量之间的题即可。",
                "相邻区间重叠时，强组落在重叠段的成员必须通过自己的专题多解题，同时题目难度还要避开会让弱组也解出的范围。",
                "简单版只有两个城市，跨两组冲突不存在，检查并构造相邻组即可，最后再验算解题数条件。",
            ],
            "solution_brief": "关键观察：构造题目不是任意凑，而是把每个城市压成力量区间。若两城市区间分离，加入两道分隔难度题；若有重叠，就给强城市重叠成员安排不冲突的专属专题题，并把难度尽量选在智慧允许且弱城市解不到的位置。构造后直接模拟验算，不满足则无解。",
            "primary_topic": "构造与贪心",
        },
        "2046B": {
            "statement_brief": "给定数组；一次操作可选一个位置，把该数加 1 后移到数组末尾。可操作任意次，求所有可达数组中字典序最小的一个。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是带“加一并移尾”操作的字典序最小可达数组问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2046A": {
            "statement_brief": "给 2 行 n 列矩阵，可任意交换整列；交换后从左上走到右下，每步向右或向下，要求路径经过的 n+1 个格子和最大。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：路径等价于选择某一列下移，该列上下两个数都取，其它列只取上行或下行。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2022A": {
            "statement_brief": "若干家庭坐一辆每排 2 座的车。同家庭两人同排会快乐，单人独坐一排也快乐；问最优安排下最多有多少快乐乘客。",
            "transformed_statement": "先把同家庭成员尽量两两成排；剩下只会是每个奇数家庭多出来的一个人，问题变成这些单人是否能各自独坐。",
            "key_observations": [
                "同家庭两人坐满一排会产生 2 个快乐乘客，并且不会占用额外空排，永远优先。",
                "处理完家庭内部配对后，只需知道剩余单人数和剩余空排数。",
                "若空排足够，所有单人都能独坐并快乐；否则一些不同家庭单人必须同排，快乐人数按被迫混坐数量减少。",
            ],
            "solution_brief": "关键观察：座位安排只看家庭内部成对数和剩余单人数。累计成对贡献并扣掉已用排数；若剩余空排不少于单人数，答案再加单人数，否则再加“剩余空排数的两倍减单人数”。",
            "primary_topic": "构造与贪心",
        },
        "2238E": {
            "statement_brief": "给一个由真蛋糕、假蛋糕和未放置位置组成的串，未放置位置可任选真假。之后回答者必须把所有假蛋糕猜成一个连续区间，求布置者能保证的最大错误数。",
            "transformed_statement": "把题目先看成：固定最终串后，回答者的最佳连续区间选择等价于在一个正负一数组里取最大子段和。",
            "key_observations": [
                "把假蛋糕记为 +1，真蛋糕记为 -1，则区间内“假减真”就是该区间和。",
                "固定最终串时，回答者会选择最大区间和来减少错误，所以最少错误等于假蛋糕总数减最大非负子段和。",
                "布置者的目标变成：替换所有未知位，使“假蛋糕总数减最大非负子段和”最大。",
                "从左到右动态规划时，记录已放假蛋糕数、当前非负后缀和，以及全局最大子段和的最小可行值。",
            ],
            "solution_brief": "关键观察：先把连续区间猜测转成最大子段和，再对未知位做动态规划。放假蛋糕会让后缀和加一并可能提高全局最大；放真蛋糕会让后缀和减一但不低于零。枚举最终假蛋糕数和后缀状态，取“假蛋糕数减最小全局最大子段和”的最大值。",
            "primary_topic": "动态规划与状态设计",
        },
        "2229A": {
            "statement_brief": "数轴上有若干史莱姆。一次选择整数 x，所有小于 x 的位置加一，所有大于 x 的位置减一，等于 x 的不变；求让它们重合的最少操作数。",
            "transformed_statement": "把题目先看成：若最终重合位置为 y，每次都选 x=y 最优，答案只由最左和最右位置到 y 的最大距离决定。",
            "key_observations": [
                "固定最终位置时，选择该位置会让所有未到达者同时朝目标走一步，不会浪费操作。",
                "因此固定终点的操作数是它到当前最小位置和最大位置的较大距离。",
                "要最小化最大距离，终点应尽量靠近最小值和最大值的中点。",
            ],
            "solution_brief": "关键观察：中间位置完全不影响答案，只看数轴直径。设最小位置为 mn、最大位置为 mx，输出 (mx-mn+1)//2。",
            "primary_topic": "基础实现与模拟",
        },
        "2207G": {
            "statement_brief": "网格中有必须染黑的格子和高价值格子；按规则每次只能染一个至多邻接一个黑格的白格，要求给出染黑顺序，使必须格全部染黑且总价值达到阈值。",
            "transformed_statement": "把题目先看成：最终黑格集合在四邻接图中必须是一片森林；若候选集合出现环，就删掉非必须、非高价值格来破环。",
            "key_observations": [
                "一个黑格集合可按规则染出，当且仅当它的四邻接图没有环；有森林后可通过遍历恢复染色顺序。",
                "三种条纹平移的平均覆盖能保证至少有一种候选方案覆盖足够多普通格。",
                "把条纹格和必须格合并后，利用平面图结构可界定需要破掉的最小环数量。",
                "高价值格不与必须格相邻，因此每个需要破掉的环上都能选到可删除的普通格。",
            ],
            "solution_brief": "关键观察：操作约束的本质是森林，而不是逐步贪心模拟。枚举三种条纹平移，选择价值足够的一种；再不断从最小环上删除普通格直到无环。得到森林后按叶子剥离或遍历顺序输出染色操作。",
            "primary_topic": "图论与网络流",
        },
        "2207D": {
            "statement_brief": "树上追逃游戏：火鼠从非叶起点出发想走到叶子，拦路者每隔 k 步才能重新封一条边。双方最优，判断火鼠能否必然逃到叶子。",
            "transformed_statement": "把题目先看成：拦路者想守住一个包含起点、内部没有叶子的连通区域；这个区域的不同出口必须相距足够远，才来得及轮流封堵。",
            "key_observations": [
                "若安全区域存在两个距离过近的出口，火鼠可以在两出口之间施压，最终等到封边冷却跟不上而逃出。",
                "叶子天然不能属于可长期困住它的区域，所以先把所有叶子标记为排除点。",
                "若两个已排除分支通过某点的距离太小，则该点也不可能留在安全区域内。",
                "自底向上维护每个点到最近排除点的距离，遇到两条近距离排除分支就把当前点也标记。",
            ],
            "solution_brief": "关键观察：不要模拟博弈，而是求“排除闭包”。以起点为根，叶子先标记；令状态值表示到最近标记点的距离。若某点两棵子树中的标记点距离和不超过限制，就把该点标记。最后起点被标记表示不存在可长期封锁的安全区域，火鼠能逃；否则拦路者能守住。",
            "primary_topic": "树结构",
        },
        "2205A": {
            "statement_brief": "给一个排列，定义位置 i 是丑位置当且仅当 i 等于前缀最大值。最多交换一次，要求输出可得到的、丑位置数量最少的排列。",
            "transformed_statement": "把题目先看成：最后一个位置必然是丑位置；只要把最大值放到第一位，就能压住前面所有前缀最大值。",
            "key_observations": [
                "位置 n 的前缀包含整个排列，前缀最大值一定是 n，所以答案下界至少为 1。",
                "若第一个数就是 n，那么任意 i<n 的前缀最大值都是 n，不可能等于 i。",
                "找到值 n 的位置并与第一项交换，正好达到下界。",
            ],
            "solution_brief": "关键观察：最大值放在首位后，除最后位置外所有前缀最大值都被固定为 n。直接把值 n 和第一项交换并输出；此时丑位置数量最少。",
            "primary_topic": "构造与贪心",
        },
        "2138E1": {
            "statement_brief": "给非负整数 x，要求构造一个不超过 80 阶的方阵，元素只为 -1、0、1，且每行每列非零元不超过 3，使行列式等于 x。",
            "transformed_statement": "把题目先看成：不要直接凑矩阵，而是把行列式展开转成有向图中的环覆盖计数，再构造一张源到汇路径数正好为 x 的无环图。",
            "key_observations": [
                "行列式展开中的每个排列，对应有向图里每个点入度出度各为一的环覆盖。",
                "给无环图加上汇点到源点的边和中间点自环后，每条源到汇路径恰好对应一个环覆盖。",
                "把原图边权设为 -1，自环和回边设为 1，排列符号与边权符号抵消，每条路径贡献都是 +1。",
                "于是只需构造一张出入度小、源汇路径数等于 x 的无环图；容易版可用三进制小模块串接完成。",
            ],
            "solution_brief": "关键观察：矩阵问题先降成路径计数问题。构造源到汇路径数为 x 的无环图；矩阵中原图边填 -1，中间点自环填 1，汇点到源点填 1。这样行列式正好等于源汇路径数，再用三进制模块控制路径数并满足稀疏限制。",
            "primary_topic": "代数、矩阵与多项式",
        },
        "2128F": {
            "statement_brief": "无向连通图每条边权可在给定上下界内任选。给定点 k，问是否存在赋权，使 1 到 n 的最短路长度不等于 1 到 k 再到 n 的最短路长度之和。",
            "transformed_statement": "把题目先看成：若存在可行赋权，就可把某条 1 到 n 的候选路径全部压到下界，路径外边全部拉到上界；问题变成寻找一条不会被经过 k 的路线追平的下界路径。",
            "key_observations": [
                "取任意可行赋权下的一条 1 到 n 最短路；降低路上边权不会让经过 k 的路线更有优势，升高路外边权也不会伤害这条路。",
                "固定候选路径后，必要且充分条件是路径上任意两点 u、v 满足：下界距离 u 到 v 小于上界距离 u 到 k 再到 v。",
                "这个条件可解释成强盗沿下界速度前进、警察和市民沿上界速度报警追击。",
                "路径搜索时只需维护一个计时器，表示警察尚未被通知多久或已经追了多久。",
            ],
            "solution_brief": "关键观察：先把连续赋权空间压到“候选路径取下界、其它边取上界”的极端形态。先从 k 按上界边权求到各点的警察距离；再从 1 做改造最短路，状态为当前计时器，过边后取“旧计时器加下界边长”和“当前位置触发报警时间”的较大值。若警察距离已不大于计时器则该状态失败；能处理到 n 就输出可行。",
            "primary_topic": "图论与网络流",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2118C": {
            "statement_brief": "数组美丽值定义为所有元素二进制表示中 1 的总数。每次可把一个元素加 1，至多操作 k 次，求能达到的最大美丽值。",
            "transformed_statement": "把题目先看成：让一个数的美丽值增加 1 的最低成本，是把它最低位的 0 变成 1；因此所有升级机会可按二进制位从低到高购买。",
            "key_observations": [
                "对整数 x，严格大于 x 且美丽值更大的最小数，就是把 x 最低位的 0 置为 1。",
                "到达这个数之前，低位进位不会产生更高美丽值，因此这一步成本是不可再降的。",
                "统计每个二进制位上有多少元素当前为 0，从低位到高位贪心购买这些升级机会。",
            ],
            "solution_brief": "关键观察：每次美丽值加一的最小代价由当前最低位 0 决定，代价为对应的二进制位权。先累计初始美丽值，再从低位到高位消耗操作次数购买升级，买得起就答案加一。",
            "primary_topic": "数论与同余",
        },
        "2071D2": {
            "statement_brief": "给出二进制无限序列前 n 项；之后第 m 项等于前 ⌊m/2⌋ 项的异或和。多次询问区间 [l,r] 内 1 的个数。",
            "transformed_statement": "把题目先看成：单点递归可以推广到前缀递归；分别维护前缀中偶数位置和奇数位置的 1 的数量。",
            "key_observations": [
                "先把 n 调成奇数并预处理到 2n，之后序列会按相邻两项成对出现。",
                "大下标项只依赖总前缀异或和以及下标折半后的奇偶层。",
                "当右端点调整到合适模数后，末尾成对部分的偶位和奇位贡献相同，都能递归折半计算。",
            ],
            "solution_brief": "关键观察：不要逐项计算区间，写前缀函数返回前 m 项中 1 的数量。预处理 2n 以内的普通前缀和、偶位前缀和；对更大的 m，先剥掉末尾少数不整齐项，再把成对区间折半递归。区间答案为两个前缀相减。",
            "primary_topic": "动态规划与状态设计",
        },
        "2030F": {
            "statement_brief": "定义数组若能反复删除同值连续块，且每个值最多作为删除目标一次，则称为可删除数组。给数组和多次区间询问，判断子数组是否可删除。",
            "transformed_statement": "把题目先看成：不可删除的本质是两个不同值交叉出现，形成 x、y、x、y 的子序列模式。",
            "key_observations": [
                "题解给出充要条件：数组不可删除，当且仅当存在两个不同值按 x、y、x、y 的顺序交叉出现。",
                "若没有交叉模式，按第一个值的所有出现位置切开，中间各段的值集合互不相交，可以递归删除。",
                "扫描右端点时，新元素只会通过它的上一次出现与当前合法左边界之间的下一次出现产生交叉。",
                "维护每个右端点对应的最小合法左端点后，询问只需判断给定左端点是否不小于它。",
            ],
            "solution_brief": "关键观察：可删除性等价于不存在 x、y、x、y 交叉子序列。预处理每个位置的上一次和下一次同值位置；右端点从左到右推进，用维护下一次出现最大值的数据结构检查交叉并移动左端点。得到每个右端点的最小合法左端点后，区间询问可常数判断。",
            "primary_topic": "数据结构",
        },
        "2247F": {
            "statement_brief": "在带障碍网格中，路径只能向右或向下。计数非空格子集合，使任意经过集合中某一格的完整路径都必须经过集合中所有格。",
            "transformed_statement": "把题目先看成：两个格子能放入同一集合，等价于它们在所有完整路径中的必经关系互相成立；这种关系可合并成强连通块。",
            "key_observations": [
                "若某个空格完全不在任何完整路径上，那么只由这类格子组成的任意非空集合都合法。",
                "对至少被某条完整路径经过的格子，能同处一个集合的格子必须满足单调路径上的偏序可比较。",
                "若格子甲在格子乙左上方，二者同集合要求所有到乙的完整路径都先经过甲，反向也要满足对应必经条件。",
                "把必经关系建成有向关系后，合法集合正好来自同一强连通块内的任意非空子集。",
            ],
            "solution_brief": "关键观察：合法集合不是任意路径交集，而是“完整路径必经关系”的互相闭合。先统计不在任何完整路径上的格子；其余格子求起点侧和终点侧的必经关系，合并互相强制的强连通块，每个块贡献 2 的块大小次方减一。",
            "primary_topic": "数据结构",
        },
        "2245H": {
            "statement_brief": "给一个非负整数网格。若两个相同正数格子之间存在一条简单路径，内部格子全为 0，且路径转弯次数不超过 2，则称这两个格子可连接；求可连接无序点对数量。",
            "transformed_statement": "本地题解正文不足，本条只从题面整理：这是网格中同值正数端点、零格内部、最多两次转弯路径的可连接点对计数问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "数据结构",
        },
        "2238C": {
            "statement_brief": "树以 1 为根。对每个中心点 v 和距离 h，v 子树中距离 v 恰好 h 的点集构成一个公会；要求统计不同的非空公会数量。",
            "transformed_statement": "把题目先看成：子树内部已有公会交给儿子统计；以当前点为中心的新公会，只取决于有多少儿子子树能延伸到同一深度。",
            "key_observations": [
                "每个点自己对应距离 0 的公会，固定贡献 1。",
                "若某一层的点全部来自同一个儿子子树，这个公会已经在该儿子的答案中出现过。",
                "真正以当前点为中心的新公会，必须在至少两个儿子子树里都能取到距离 h 的点。",
                "满足这个条件的 h 的数量，正好等于所有儿子向下最大延伸深度中的第二大值。",
            ],
            "solution_brief": "关键观察：每个点的新贡献不是最大深度，而是第二大儿子延伸深度。深搜求每个子树最大深度；回溯时取当前点儿子的两个最大延伸值，答案为 1 加第二大延伸值再加所有儿子答案。",
            "primary_topic": "树结构",
        },
        "2226B": {
            "statement_brief": "若数组最大值减最小值等于全体元素的最大公约数，则称其为好数组。给一个排列，求其中好子数组的数量。",
            "transformed_statement": "把题目先看成：除以整体最大公约数后，最大值和最小值必须是相邻整数；排列元素互异又把候选压缩到长度为 2 的子数组。",
            "key_observations": [
                "设整体最大公约数为 g，最大值为 Mg，最小值为 mg，好数组条件化为 M-m=1。",
                "因此数组里只能出现相邻的两个 g 的倍数；而排列没有重复元素，长度超过 2 时无法满足。",
                "只需检查每个相邻二元组是否满足“较大值减较小值等于二者最大公约数”。",
            ],
            "solution_brief": "关键观察：最大公约数归一化后，好数组只能由相邻的两种倍数组成；排列性进一步说明只可能是相邻两个元素。线性扫描所有相邻对，满足条件就计数。",
            "primary_topic": "数论与同余",
        },
        "2190D": {
            "statement_brief": "给一片森林，统计所有把它补成树的方案中，普吕弗删除过程最后除 n 外留下的另一个点分别是谁。",
            "transformed_statement": "把题目先看成：补成树后最终留下的普吕弗顶点，就是从 n 到 n-1 路径上紧邻 n 的那个点；于是问题转成森林补边计数。",
            "key_observations": [
                "编号 n-1 只有在最后和 n 同时作为两个叶子时才可能不提前被删。",
                "因此固定一棵树后，最终留下的非 n 点就是 n 到 n-1 路径上的第二个点。",
                "补森林时，同一连通块内的点在连接计数上对称，只需按连通块大小分摊贡献。",
                "枚举候选点，按它与 n、n-1 所在连通块的关系分类计算补边方案数。",
            ],
            "solution_brief": "关键观察：不用模拟完整普吕弗过程，只看 n 到 n-1 的路径第二点。先求连通块和以 n 所在块为根时的子树大小；再按候选点是否在 n 所在块、n-1 所在块或其它块分类，把补成树的总方案数乘上对应比例。",
            "primary_topic": "组合计数与概率",
        },
        "2187C": {
            "statement_brief": "在特殊无交叉有向图上进行追逃游戏：杰瑞每回合必须沿出边走，汤姆可走可停并想最少移动次数抓到杰瑞。求所有起点对的答案和。",
            "transformed_statement": "把题目先看成：每个点只保留能到达最远位置的出边，这些边形成一棵以 n 为根的树；追逃值变成树上最近公共祖先公式。",
            "key_observations": [
                "由于额外边不交叉，走到更远终点的出边支配同一起点的其它出边。",
                "每点最远出边构成一棵指向 n 的树，树深度表示还要走多少步到终点。",
                "若杰瑞到根更近，汤姆追不上；否则汤姆只需移动到两点的最近公共祖先等待。",
                "所有点对贡献可拆成深度最小值、最近公共祖先深度和同深度修正三部分统计。",
            ],
            "solution_brief": "关键观察：原图先压成最远出边树。无交叉性质保证双方都走最远边最优，所以单对答案只与两点深度和最近公共祖先有关；总和用排序、子树大小和树上小并大分别统计三个拆项。",
            "primary_topic": "树结构",
        },
        "2174C1": {
            "statement_brief": "长度 n 的随机颜色串，每个位置独立均匀从 m 种颜色中选。定义正确度为非空回文子段数量，美丽值为正确度平方；求美丽值期望模质数。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：目标是计算所有回文子段有序对同时成立的概率之和。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "组合计数与概率",
        },
        "2157H": {
            "statement_brief": "要求输出最多 2000 个长度为 n 的单峰排列，使其作为置换时恰好有 m 个循环。",
            "transformed_statement": "把题目先看成：先构造等价的反单峰排列；小规模枚举作为种子，再用两个扩展操作推到更大的 n。",
            "key_observations": [
                "单峰排列与反单峰排列可通过反转并取补建立双射，后者更方便构造。",
                "已有 (n,m) 的解时，末尾追加 n+1 可得到 (n+1,m+1) 的解。",
                "已有 (n,m) 的解时，末尾追加 n+1 后再调整第一项，可得到 (n+1,m) 的解。",
                "当 n-m 很小时，循环很多意味着固定点很多，反单峰结构会迫使第一项很小，只需枚举小前缀。",
            ],
            "solution_brief": "关键观察：不要直接搜索 n 到 100 的全空间。小 n 直接枚举反单峰排列；当 n 很大且 n-m 不小时，从 n=18 的种子解用两个扩展操作推上去；当 n-m 很小时，利用固定点数量限制第一项，只枚举很短前缀，最后映射回单峰排列输出。",
            "primary_topic": "构造与贪心",
        },
        "2129B": {
            "statement_brief": "给一个排列。每个位置可保留原值，或改成 2n 减原值；要求最小化最终数组逆序对数量。",
            "transformed_statement": "把题目先看成：对每个原值，它只会和比它大的元素产生选择代价；选择小值看左边更大数，选择大值看右边更大数。",
            "key_observations": [
                "若保留原值，它作为较小值时，只会与左侧比它大的元素形成逆序。",
                "若改成 2n 减原值，它变成大值，只会与右侧比它大的元素形成逆序。",
                "这两种代价只取决于当前位置左右两侧比它大的元素数量，和其它位置的选择无关。",
                "因此每个位置可独立取左右代价较小者。",
            ],
            "solution_brief": "关键观察：每个位置的二选一代价彼此独立。对每个位置统计左侧比它大的个数和右侧比它大的个数，答案累加二者较小值；总规模允许直接平方统计。",
            "primary_topic": "构造与贪心",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2109D": {
            "statement_brief": "给定无向连通图和一个步长多重集；每次取出一个步长并走恰好这么多条边。对每个点独立判断，能否从 1 号点出发用某个子多重集走到它。",
            "transformed_statement": "把题目先看成：能否到达某点只关心总步数的奇偶和是否足够长，因为任意游走都能插入来回边多走 2 步。",
            "key_observations": [
                "对每个点只需求从 1 到它的最短偶长度和最短奇长度，可在“点加奇偶”状态图上广搜得到。",
                "使用全部步长时，总长度固定；若某点对应奇偶的最短长度不超过它，就能通过来回边补足。",
                "若要改变总长度奇偶，只能删去一个奇数步长；删除最小奇数损失最少。",
            ],
            "solution_brief": "关键观察：图上游走长度只分奇偶，长度不足可以用来回边补 2。先广搜出每个点的最短偶游走和最短奇游走；设所有步长总和为 S，若对应奇偶可达则输出可达，否则尝试删除最小奇数步长后检查相反奇偶。",
            "primary_topic": "图论与网络流",
        },
        "2081G1": {
            "statement_brief": "给定 n，计算所有 k 从 1 到 n 的 k 对欧拉函数值取模之和，最后对 2 的 32 次方取模。",
            "transformed_statement": "把题目先看成：把余数写成 k 减去欧拉函数值乘以二者商的整数部分，核心是统计这个整数部分何时变化。",
            "key_observations": [
                "k 与欧拉函数值的比值只由 k 的不同质因子集合决定。",
                "若乘入新质因子会改变比值的整数部分，则这个质因子必须足够小；题解给出了对应上界。",
                "因此大质因子可用欧拉函数在质数上的前缀和批量贡献，小质因子组合再递归枚举。",
            ],
            "solution_brief": "关键观察：直接枚举到 n 不可能，要枚举“会改变商整数部分”的质因子集合。把答案拆成等差和减去若干欧拉函数贡献；小质因子递归扩展状态，大质因子用质数欧拉函数前缀和一次汇总。",
            "primary_topic": "数论与同余",
        },
        "2049D": {
            "statement_brief": "网格每行可在出发前循环左移任意次，每次位移有固定花费。之后只能向右或向下走到右下角，求位移花费和路径格子和的最小总成本。",
            "transformed_statement": "把题目先看成：进入每一行时单独选择该行的循环位移，然后在这一行内向右走若干步再向下。",
            "key_observations": [
                "每一行的位移只影响这一行访问到的格子，与其它行的位移选择可以在动态规划中分开枚举。",
                "处理第 i 行时，枚举本行左移量，并维护在该行内走到每一列的最小代价。",
                "转移只有两种来源：从上一行同列向下进入，或从本行左侧继续向右走。",
            ],
            "solution_brief": "关键观察：不要枚举所有行位移组合，只把位移作为当前行状态。对每行枚举左移量，先用上一行答案加位移费用和当前格值初始化，再沿本行向右松弛；所有左移量取最小后成为这一行的答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2046E2": {
            "statement_brief": "有任意多个城市组的参赛者，每人有力量、专题和智慧。要构造不超过 5n 道专题各不相同的题，使城市编号越小的任意参赛者解题数严格越多；无解则输出 -1。",
            "transformed_statement": "把题目先看成：城市组的力量区间必须形成只允许相邻冲突的链；每个相邻冲突再转成专题和难度的避让约束。",
            "key_observations": [
                "若第 i 组最低力量不大于第 i+2 组最高力量，两组间至少需要差 2 题，但专题能力最多补 1 题，直接无解。",
                "相邻组区间分离时，只需加入少量难度落在两区间之间的题来拉开解题数。",
                "相邻组区间重叠时，强组重叠成员必须靠自己的专题多解题，同时难度要避开弱组凭力量或专题解出的范围。",
                "困难版需要维护未使用专题和禁用难度区间，构造后再模拟校验严格性。",
            ],
            "solution_brief": "关键观察：先用每组力量最小值和最大值做全局剪枝，保证只剩相邻组需要处理。对每个相邻组，区间分离就放分隔难度题；区间重叠就为强组相关成员选择未冲突专题和允许难度。全部构造完成后直接验算所有城市间解题数关系。",
            "primary_topic": "构造与贪心",
        },
        "2040B": {
            "statement_brief": "长度为 n 的数组初始全为 0。一类操作可把单个 0 变 1；二类操作可选择两端为 1 且 1 的数量不少于区间一半的区间，把整个区间变 1。求最少一类操作次数。",
            "transformed_statement": "把题目先看成：一类操作负责播种新的 1，二类操作负责把已有 1 的密度扩张成更长的连续段。",
            "key_observations": [
                "任意时刻数组中的 1 形成若干不相交连续段。",
                "一次一类操作最多让连续段数量加一；一次二类操作若覆盖多个连续段，会把段数合并减少。",
                "因此二类操作次数不可能超过一类操作次数减一。",
                "最优策略是先放一个 1，之后每多放一个 1，就用一次二类操作把可覆盖长度翻到约两倍。",
            ],
            "solution_brief": "关键观察：只需模拟最优扩张长度。初始一次一类操作覆盖长度为 1；之后每增加一次一类操作，就接一次二类扩张，使覆盖长度变为原长度加一后的两倍。直到覆盖 n，使用的一类操作次数即答案。",
            "primary_topic": "构造与贪心",
        },
        "2027B": {
            "statement_brief": "定义可脆弱数组：能对若干子数组执行斯大林排序，最终变成非递增。给数组，求最少删除多少元素能让它可脆弱。",
            "transformed_statement": "把题目先看成：数组可脆弱当且仅当首元素是全局最大值；所以要保留一个以某个位置开头、后面元素都不大于它的最长子序列。",
            "key_observations": [
                "若首元素是最大值，对整个数组执行一次斯大林排序即可得到非递增序列。",
                "若最大值不在首位，任何子数组操作都不会删除首元素，也不会删除全局最大值，最终必然破坏非递增。",
                "枚举删除后保留子序列的首元素，右侧只能保留不大于它的元素。",
            ],
            "solution_brief": "关键观察：别模拟多次排序，直接用“首元素必须是最大值”的充要条件。枚举原数组哪个位置作为保留后的首位，保留它和右侧所有不大于它的元素，最大保留长度的补集大小就是最少删除数。",
            "primary_topic": "构造与贪心",
        },
        "2020B": {
            "statement_brief": "n 个灯泡初始全亮；对每个 i 翻转所有编号为 i 的倍数的灯。要求最终亮灯数恰好为 k，求最小 n。",
            "transformed_statement": "把题目先看成：第 x 个灯会被翻转“x 的约数个数”次；最终仍亮当且仅当 x 不是完全平方数。",
            "key_observations": [
                "每个灯的最终状态只取决于它自身编号，与更大的 n 无关。",
                "非平方数的约数成对出现，约数个数为偶数；完全平方数多出平方根这个自配对约数，约数个数为奇数。",
                "所以前 n 个灯中亮着的数量等于 n 减去不超过 n 的完全平方数个数。",
            ],
            "solution_brief": "关键观察：亮灯数就是非完全平方数个数。二分最小 n，使 n-⌊√n⌋ 至少为 k；这个函数单调。题解也给出直接式，但二分实现更稳。",
            "primary_topic": "数论与同余",
        },
        "2018F2": {
            "statement_brief": "中等版要求对每个 k 统计截止时间数组数量，使原征服城市问题中恰好有 k 个可获胜起点。",
            "transformed_statement": "把题目先看成：固定可赢起点区间长度后，不同位置的约束只是同一长数组上的滑动窗口，可共用一次区间动态规划。",
            "key_observations": [
                "可赢起点集合仍然只能为空，或为一个连续区间。",
                "固定可赢区间后，每个城市的截止时间有由区间两端决定的下界。",
                "相同长度的区间共享同一种下界形状，只是整体平移。",
                "把所有平移嵌入长度 2n 的统一下界数组，每个长度只需跑一次动态规划。",
            ],
            "solution_brief": "关键观察：相同长度的可赢区间共享约束形状。枚举区间长度，在长度 2n 的循环式下界数组上做区间动态规划；其中长度为 n 的窗口对应实际位置。再用区间容斥扣掉包含更大可赢区间的情况，得到每个 k 的计数。",
            "primary_topic": "动态规划与状态设计",
        },
        "2018F1": {
            "statement_brief": "简单版要求对每个 k 统计截止时间数组数量，使原征服城市问题中恰好有 k 个可获胜起点。",
            "transformed_statement": "把题目先看成：先枚举非空可赢起点区间，统计至少让这个区间全可赢的数组，再用容斥得到恰好这个区间。",
            "key_observations": [
                "固定起点若存在获胜策略，题解中的确定性策略也能获胜。",
                "所有可赢起点不是零散集合，而是空集或一个连续区间。",
                "固定区间后，每个城市的截止时间至少要达到它到区间两端的较大距离加一。",
                "计数访问顺序比直接计数数组更方便，再除去同一数组对应的重复起点数。",
            ],
            "solution_brief": "关键观察：把“多少起点能赢”转成“哪个区间整体能赢”。简单版可枚举区间，用确定性策略做区间动态规划：从已访问区间向左右扩张并检查新城市截止时间下界。得到至少包含该区间的计数后，用二维容斥扣掉更大区间，最后按区间长度汇总。",
            "primary_topic": "动态规划与状态设计",
        },
        "2005D": {
            "statement_brief": "给两个长度相同的数组，必须恰好选择一个连续区间，并交换该区间内两数组对应位置的元素。求交换后两数组最大公约数之和的最大值，以及达到最大值的区间数量。",
            "transformed_statement": "本地题解正文不足，本条只从题面整理：这是一次区间交换后优化两数组整体最大公约数之和，并计数最优区间的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "数论与同余",
        },
        "2258F": {
            "statement_brief": "给一棵有根树，点权初始为 -1、0 或 1。所有 0 点需改成 -1 或 1，求所有子树权值和绝对值之和的最小值。",
            "transformed_statement": "把题目先看成：每个子树只关心最终有多少个 1；朴素树形动态规划的代价序列具有凸性，可以只维护差分并小并大合并。",
            "key_observations": [
                "朴素做法是对每个点按子树内 1 的数量维护最小代价。",
                "合并两个儿子时，相当于合并两个凸代价函数，合并后的序列仍保持凸性。",
                "凸序列可用首项和相邻差分表示，儿子合并就变成差分集合的合并。",
                "对子树和绝对值的贡献，只需在零点附近调整差分；配合小并大可降复杂度。",
            ],
            "solution_brief": "关键观察：树形动态规划表不是任意数组，而是凸代价序列。用差分表示每个点的代价函数，合并儿子时小并大合并差分集合，再加入当前子树绝对值项对差分的影响，最终根的最小值就是答案。",
            "primary_topic": "动态规划与状态设计",
        },
        "2245G": {
            "statement_brief": "交互题。隐藏一棵无向树；一次询问给出一个点序列，交互器按顺序贪心返回其中一个独立集。总询问长度受限，要求恢复所有边。",
            "transformed_statement": "把题目先看成：询问两个独立集的拼接，可以识别后一个集合里哪些点与前一个集合至少有一条边。",
            "key_observations": [
                "任意询问返回的集合都是独立集。",
                "若两个集合本身都是独立集，先放第一个集合再放第二个集合，则第一个集合会全被选中；第二个集合中未被选中的点正是与第一个集合相邻的点。",
                "已知一侧集合与另一侧每个点都至少有边时，可以把一侧二分递归找出所有跨边。",
                "整体递归时，先用一次询问把当前点集切出独立集；剩余诱导图是森林，可二染色成两个独立集，再分别找跨边。",
            ],
            "solution_brief": "关键观察：交互返回的贪心独立集可以当成切分器。递归处理当前点集：询问得到独立集，先递归恢复剩余点内部边；由于剩余部分仍是森林，将其二染色成两个独立集，再用二分查边过程恢复跨边。摊还分析保证总询问长度不超限。",
            "primary_topic": "交互",
        },
    }
)

PROBLEM_OVERRIDES.update(
    {
        "2005A": {
            "statement_brief": "构造一个长度为 n、只由五个小写元音组成的字符串，使其中回文子序列数量最少。",
            "transformed_statement": "把题目先看成：先决定五种元音各出现几次，再用分块排列避免产生跨字母的回文子序列。",
            "key_observations": [
                "只由同一种元音组成的非空子序列一定是回文，若该元音出现 c 次，就贡献 2^c-1。",
                "把相同元音连续放成五个块时，不会额外产生两端同字母夹其它字母的回文子序列，下界可达到。",
                "指数函数是凸的，所以五种元音出现次数应尽量平均，任意两种次数差不超过 1。",
            ],
            "solution_brief": "关键观察：最少回文子序列来自“每种元音数量尽量平均，并按元音分块输出”。把 n 平均分到五个元音上，前 n mod 5 个元音多放一个，然后按固定顺序输出各自连续块。",
            "primary_topic": "构造与贪心",
        },
        "2005B1": {
            "statement_brief": "一维教室中有两名老师和一名学生；每回合学生先移动或停留，老师再同时移动或停留。双方最优，求老师抓到学生需要多少步。",
            "transformed_statement": "把题目先看成：只有学生相对两名老师的位置关系重要，分为在两老师左侧、中间、右侧三种情况。",
            "key_observations": [
                "若学生在两名老师外侧，他会向最近边界逃，答案等于最近老师到该边界的距离。",
                "若学生在两名老师中间，两边老师夹逼，学生最多拖到区间中点。",
                "因此只需取左右老师位置排序后按三种位置关系套公式。",
            ],
            "solution_brief": "关键观察：两名老师足够把问题压成一维夹逼。设老师位置为 l<r、学生为 x；若 x<l，答案为 l-1；若 x>r，答案为 n-r；否则答案为 (r-l)//2。",
            "primary_topic": "构造与贪心",
        },
        "2005B2": {
            "statement_brief": "困难版有多名老师和多次询问。每次给学生初始位置，双方最优，求老师抓到学生需要多少步。",
            "transformed_statement": "把题目先看成：每个询问只需要学生左右最近的老师；更远的老师不会改善最优夹逼结果。",
            "key_observations": [
                "若学生在最左老师左侧或最右老师右侧，答案只由最近边界和最近老师决定。",
                "若学生夹在两名相邻老师之间，其它老师更远，不会比这两名老师更早抓到他。",
                "把老师位置排序后，对每个询问找前驱和后继即可复用 简单版公式。",
            ],
            "solution_brief": "关键观察：多老师查询退化为最近左右老师夹逼。排序老师位置；每个学生位置用二分找右侧第一个老师和左侧最后一个老师，再按外侧或中间三种情况计算答案。",
            "primary_topic": "构造与贪心",
        },
        "2013D": {
            "statement_brief": "给数组；一次操作可把某个位置减 1，并把右侧相邻位置加 1。可操作任意次，求最终最大值与最小值差的最小可能值。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是只能把数值向右搬运时，最小化全局极差的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "构造与贪心",
        },
        "2089B2": {
            "statement_brief": "困难版给两个循环序列；先必须对第一个序列做恰好 k 次减一修改，之后每轮两序列对应抵消，再把第一个序列循环右移。求第一个序列全为 0 的最少轮数。",
            "transformed_statement": "把题目先看成：二分轮数，判断要在这么多轮内清空第一个序列，至少需要多少次预先减一。",
            "key_observations": [
                "直接在环上算贡献会重叠，先把两序列差的前缀和循环平移到末尾为全局最小的位置，可把问题线性化。",
                "固定轮数后，从右往左贪心：若后面窗口的最小前缀差大于当前位置，就必须在相邻位置补足差额。",
                "窗口最小值可用单调栈或单调队列维护，从而快速完成判定。",
            ],
            "solution_brief": "关键观察：先把环切在前缀差最小处，再二分答案。判定时在展开后的线性链上维护长度为 x 的后缀窗口最小值；每当窗口最小值仍高于当前位置，就说明必须消耗预减操作补差。所需操作不超过 k 即可行。",
            "primary_topic": "数据结构",
        },
        "2129C1": {
            "statement_brief": "交互题。隐藏括号串只含左括号和右括号，且两种括号都至少出现一次。每次可询问若干下标组成的串，并得到其中非空合法括号子串数量；简单版要求在 550 次询问内恢复原串。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是利用合法括号子串计数查询来恢复隐藏括号串的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2129C2": {
            "statement_brief": "交互题。隐藏括号串只含左括号和右括号，且两种括号都至少出现一次。每次可询问若干下标组成的串，并得到其中非空合法括号子串数量；中等版要求在 200 次询问内恢复原串。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是利用合法括号子串计数查询来恢复隐藏括号串的问题，询问次数限制比 简单版更紧。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2165D": {
            "statement_brief": "给一个整数序列，要把所有元素划分成若干子序列，使每个子序列相邻元素差的绝对值都为 1；求最少子序列数量。",
            "transformed_statement": "把题目先看成：每成功匹配一个元素到它后面值相差 1 的元素，就能少开一条路径；目标是最大化这种合法相邻匹配数。",
            "key_observations": [
                "问题可转成二分图匹配：左侧每个位置尝试连向右侧后方且值差为 1 的位置。",
                "按值奇偶分开后，边结构很有序，可用从小到大的贪心替代通用匹配。",
                "对值 v 的未匹配点，优先匹配右侧最近的 v+1；若最优解没这么配，可以交换到更近位置且不变差。",
                "也可从霍尔条件看匹配缺口，但本题有序结构让线性贪心足够。",
            ],
            "solution_brief": "关键观察：最少路径数等于元素数减去最大相邻合法匹配数。分别处理奇偶值层，按值从小到大，让未匹配的 v 尽量接到右侧最近的 v+1，另一方向同理；交换论证保证最近匹配不会损失最优性。",
            "primary_topic": "图论与网络流",
        },
        "2187F2": {
            "statement_brief": "给出两段深度优先遍历序列，计数有多少棵有根树能同时产生这两段序列。",
            "transformed_statement": "把题目先看成：两段遍历序中相对顺序冲突的孩子会形成纠缠集合；这些集合在合法树中必须作为连续块递归处理。",
            "key_observations": [
                "若两个孩子在两段遍历中的相对顺序不同，就把它们视为纠缠；极大纠缠集合及其子树点集在两段序列中都必须是连续区间。",
                "叶子相关的单点纠缠集合必须在两段序列中都位于最后，否则无法满足最优树结构。",
                "同一个极大纠缠集合在任何合法树中必须挂在同一个父节点下。",
                "大小大于 1 的纠缠集合可缩成一个叶子，内部方案递归计算；缩完后两段序列相同，转成带强制叶子的括号序列计数动态规划。",
            ],
            "solution_brief": "关键观察：两段遍历的冲突不是逐点修补，而是按极大纠缠集合整体折叠。先找出在两序列中都连续的纠缠块，递归计算块内方案；把大块缩成叶子后，剩余问题变成单一深搜序能对应多少棵树，并用括号序列动态规划处理强制叶子限制。",
            "primary_topic": "树结构",
        },
        "2205C": {
            "statement_brief": "有 n 篇博客，每篇按顺序提到若干用户。发布一篇博客时，提到的用户会按顺序被移到最近提及列表开头或插入开头。可任意安排发布顺序，求最终列表字典序最小值。",
            "transformed_statement": "把题目先看成：最终列表从前往后等价于倒着处理博客；每篇博客里只有每个用户最后一次出现会影响结果。",
            "key_observations": [
                "同一篇博客中，一个用户被多次提到时，只有最后一次会决定它相对其它用户的位置。",
                "倒序看发布过程时，若某用户已在结果中出现，再遇到它就可以忽略；否则把它追加到结果末尾。",
                "因此每一步应在剩余博客的去重后序列中，选择字典序最小的一篇放到倒序结果里。",
            ],
            "solution_brief": "关键观察：倒着做后，操作从“移到开头”变成“首次出现追加到末尾”。先把每篇博客反向去重，随后重复选择当前去掉已出现用户后的字典序最小博客，输出其中尚未出现的用户并标记。",
            "primary_topic": "构造与贪心",
        },
        "2205D": {
            "statement_brief": "给一个排列；若不存在内部位置大于等于左右邻居，则数组很酷。每次可选择一个局部峰并删除它左邻或右邻，求变成很酷所需最少操作数。",
            "transformed_statement": "把题目先看成：要最少删除，就是保留尽量长的元素链；全局最大值永远不能被删，并会把左右两侧拆成独立子问题。",
            "key_observations": [
                "全局最大值不可能作为被删除的邻居，因为只有更大的局部峰才能删除它。",
                "围绕最大值左右两侧会递归成相同问题，每侧的最大值也必须被保留。",
                "这正好对应最大笛卡尔树：从根到某个节点的一条路径就是一种可保留链。",
                "最大可保留数量等于笛卡尔树最大深度，因此答案为 n 减去该深度。",
            ],
            "solution_brief": "关键观察：删除过程的骨架是最大笛卡尔树。构建排列的最大笛卡尔树，计算每个节点深度；最长根到点路径就是最多能留下的元素数，最少操作数为 n 减最大深度。",
            "primary_topic": "树结构",
        },
        "2207H2": {
            "statement_brief": "交互题。隐藏一个按变量顺序由最小值和最大值嵌套构成的函数。可询问若干输入值并得到函数值；中等版要求在询问限制内还原函数，再回答后续求值。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是通过函数值查询还原有序最小值/最大值表达式树的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "交互",
        },
        "2208D1": {
            "statement_brief": "原本有一棵无向树，后来给每条边任意定向；现在只给出所有有序点对之间是否可达，要求判断是否存在对应的定向树并构造一棵。",
            "transformed_statement": "本地题解正文为空，本条只从题面整理：这是从可达矩阵反推出一棵有向树结构的问题。",
            "key_observations": [],
            "solution_brief": "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据旧总结或宽标签补写题解。",
            "extraction_status": "missing_editorial",
            "primary_topic": "图论与网络流",
        },
        "2231F": {
            "statement_brief": "给一个图，点为 1..n，若两点编号差的绝对值是完全平方数则连边。多次询问两点间最短距离。",
            "transformed_statement": "把题目先看成：答案不会超过 4；只需快速判断距离为 1、2、3 的情况，剩余就是 4。",
            "key_observations": [
                "拉格朗日四平方定理保证任意差值都可拆成不超过四个平方数，因此图中距离最多为 4。",
                "距离为 1 当且仅当两点编号差本身是完全平方数。",
                "距离为 2 可通过预处理“两个平方和”和“两个平方差”两类可达形式常数判断。",
                "距离为 3 时枚举第一跳的平方长度，再检查剩余是否能两步到达。",
            ],
            "solution_brief": "关键观察：四平方定理把最短路答案压到 4 以内。先预处理每个差值能否表示为两平方和，以及需要向区间外跳的两平方差条件；询问时依次判 1 步、2 步。若不行，枚举不超过 √n 个第一跳平方，检查新点到终点是否 2 步可达；仍不行则为 4。",
            "primary_topic": "数论与同余",
        },
    }
)

ENGLISH_ALLOWED_WORDS = {
    "alice",
    "bob",
    "david",
    "easy",
    "hard",
    "hao",
    "jack",
    "kevin",
    "lucas",
    "lct",
    "nim",
    "narek",
    "yes",
    "no",
}

STORY_OR_SHELL_PATTERN = re.compile(
    r"Having |Recently|One day|There (?:are|is)|You can hack only|The first line|Input|Output|Rate the problem|Problem Setting|Main Ideas First|Vote for your solution|Unable to parse markup|Good Problem|Okay Problem|Bad Problem",
    re.IGNORECASE,
)

STORY_PREFIXES = (
    "having ",
    "recently",
    "one day",
    "today,",
    "at your",
    "for a long time",
    "it's already",
    "steve made",
    "now that",
    "because he is",
    "after summoning",
    "alice is preparing",
    "even after",
    "rostam",
    "alvaro",
    "álvaro",
    "otterz",
)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def problem_key(record: Mapping[str, Any]) -> str:
    return f"{record['contest_id']}{record['index']}"


def strip_statement_shell(text: str) -> str:
    text = normalize_space(text)
    if " Add tag " in text:
        text = text.split(" Add tag ", 1)[1]
    text = re.sub(
        r"\bThis is the (?:hard|easy) version of the problem\..*?You can hack only if you solved all versions of this problem\.\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bThe difference between the versions is that.*?You can hack only if you solved all versions of this problem\.\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bYou can hack only if you solved all versions of this problem\.\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    for marker in (" Tutorials ", " Submissions ", " Examples ", " Example "):
        if marker in text:
            text = text.split(marker, 1)[0]
    for marker in (
        " The first line of the input",
        " Each test contains",
        " The first line contains",
        " Input",
        " For each test case, output",
    ):
        if marker in text and len(text.split(marker, 1)[0]) > 120:
            text = text.split(marker, 1)[0]
            break
    return normalize_space(text)


def strip_editorial_shell(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"Unable to parse markup \[type=CF_MATHJAX\]", " ", text)
    text = re.sub(r"Vote for your solution!.*?(?=\b(?:Hint|Solution|Observation|Notice|We|Let|Consider)\b)", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\bMain Ideas First,\s*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bProblem Setting:\s*[A-Za-z0-9_ .,'’/-]{0,90}\bSolution\b", " Solution ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^\s*\d{4}[A-Z][A-Z0-9]*\s+-\s+.*?(?=\b(?:Hint|Idea|Solution|Key observation|Observation|Notice|Observe|Theorem|Claim|Let's|We|Consider)\b)",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(
        r"\b(?:Idea|Preparation|Author|Editorial|Solution|Problem credits)\s*:\s*[A-Za-z0-9_ .,'’/-]{0,90}",
        " ",
        text,
    )
    cut_patterns = [
        r"\n\s*Code\s*\n",
        r"\n\s*Code\s*$",
        r"\bCode\s+(?:#include|\d{6,}|using namespace|typedef|const\s|int\s+main|ll\s)",
        r"\n\s*Rate the problem\b",
        r"\n\s*My submission\b",
        r"\n\s*Video Editorial\b",
        r"\bRate the problem\b",
        r"\bMy submission\b",
        r"\bVideo Editorial\b",
    ]
    for pattern in cut_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            text = text[: match.start()]
    text = re.sub(r"\b\d{8,}\b", "", text)
    text = re.sub(r"\bHint\s*\d*[:：]?", " ", text, flags=re.IGNORECASE)
    return normalize_space(text)


def split_sentences(text: str) -> list[str]:
    text = normalize_space(text)
    text = re.sub(r"\b(Hint|Step|Theorem|Claim|Observation)\s+(\d+)[:：]?", r". \1 \2: ", text)
    text = re.sub(
        r"\b(Your task is|You need to|You have to|What is|Please solve|Please calculate|For each query|For each option)",
        r". \1",
        text,
    )
    pieces = re.split(r"(?<=[.!?。！？])\s+|\s{2,}", text)
    result: list[str] = []
    for piece in pieces:
        piece = normalize_space(piece)
        if 18 <= len(piece) <= 700:
            result.append(piece)
    return result


def trim_text(text: str, limit: int) -> str:
    text = normalize_space(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def apply_common_rewrites(text: str) -> str:
    result = text
    for pattern, replacement in COMMON_REWRITES:
        if pattern.search(result):
            return replacement
    return result


def clean_latex(text: str) -> str:
    result = text.replace("$$$", "")
    result = re.sub(r"Unable to parse markup \[type=CF_MATHJAX\]", " ", result)
    result = result.replace("\\,", " ")
    result = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", result)
    result = re.sub(r"\\binom\{([^{}]*)\}\{([^{}]*)\}", r"C(\1,\2)", result)
    result = re.sub(r"\\(?:mathtt|text|operatorname)\{([^{}]*)\}", r"\1", result)
    result = re.sub(r"\\mathcal\{O\}", "O", result)
    result = re.sub(r"\(\^\{(?:\\text\{[^{}]*\}|\\dagger|\\ddagger|[^{}]*)\}\)", "", result)
    result = re.sub(r"\\leq\b|\\le(?![A-Za-z])", "<=", result)
    result = re.sub(r"\\geq\b|\\ge(?![A-Za-z])", ">=", result)
    result = re.sub(r"\\lt\b|\\lt(?![A-Za-z])", "<", result)
    result = re.sub(r"\\gt\b|\\gt(?![A-Za-z])", ">", result)
    result = result.replace("\\left", "").replace("\\right", "")
    result = result.replace("\\ldots", "...")
    result = result.replace("\\bmod", "mod")
    result = result.replace("\\cdot", "*")
    result = result.replace("\\oplus", "⊕")
    result = result.replace("\\times", "×")
    result = result.replace("\\sum", "求和")
    return result


def apply_post_rewrites(text: str) -> str:
    result = text
    for pattern, replacement in POST_REWRITES:
        result = pattern.sub(replacement, result)
    result = result.replace("No of", "数量")
    result = result.replace("Does there exists", "是否存在")
    result = result.replace("Lets fix", "先固定")
    return result


def light_translate(text: str) -> str:
    result = clean_latex(text)
    result = apply_common_rewrites(result)
    for src, dst in TRANSLATIONS:
        result = re.sub(rf"\b{re.escape(src)}\b", dst, result, flags=re.IGNORECASE)
    result = clean_latex(result)
    result = apply_post_rewrites(result)
    return trim_text(result, 520)


def sentence_score(sentence: str, cues: Iterable[str], position: int) -> int:
    lower = sentence.lower()
    score = max(0, 18 - position)
    if re.match(r"^\d{4}[a-z][a-z0-9]*\s+-", lower):
        score -= 120
    if lower.startswith(("the first line", "in the first line", "each test contains", "the description of")):
        score -= 100
    if lower.startswith(("this is the easy version", "this is the hard version", "note:", "the difference between")):
        score -= 90
    if lower.startswith(STORY_PREFIXES):
        score -= 80
    if lower.startswith("proof:"):
        score -= 65
    if lower.startswith(("theorem", "claim", "key observation", "observation")):
        score += 65
    if any(noise in lower for noise in TITLE_NOISE):
        score -= 45
    if "your task is" in lower or lower.startswith(("find ", "determine ", "count ", "construct ", "help ", "calculate ", "what is ")):
        score += 70
    if (
        "wants to know" in lower
        or "you need to find" in lower
        or "you have to find" in lower
        or "you want to find" in lower
        or "please calculate" in lower
        or "aims to maximize" in lower
        or "aims to minimize" in lower
        or "asked you to construct" in lower
        or "would like to" in lower
        or "have to find" in lower
        or "have to deduce" in lower
        or "you should determine" in lower
        or "the task is to" in lower
        or "please solve" in lower
    ):
        score += 60
    for cue in cues:
        if cue in lower:
            score += 20
    if "code" in lower or "#include" in lower or "signed main" in lower:
        score -= 100
    if len(sentence) > 520:
        score -= 6
    return score


def sentence_is_input_noise(sentence: str) -> bool:
    lower = sentence.lower()
    return lower.startswith(
        (
            "the first line",
            "in the first line",
            "each test contains",
            "the description of",
            "the next line",
            "the following line",
            "for each test case, output",
            "you can hack only",
            "this is the easy version",
            "this is the hard version",
            "the difference between",
            *STORY_PREFIXES,
        )
    )


def sentence_is_editorial_noise(record: Mapping[str, Any], sentence: str) -> bool:
    lower = sentence.lower()
    title = str(record.get("title") or "").lower()
    if "code" in lower or "#include" in lower or "signed main" in lower or "using namespace" in lower:
        return True
    if "my submission" in lower or "video editorial" in lower or "rate the problem" in lower:
        return True
    if "unable to parse markup" in lower or "vote for your solution" in lower:
        return True
    if lower.startswith(("problem setting:", "with a time complexity", "however, this solution does not help", "implementation")):
        return True
    if "easy version" in title and "hard version" in lower:
        return True
    return False


def pick_top_sentences(
    text: str,
    cues: Iterable[str],
    limit: int,
    record: Mapping[str, Any] | None = None,
    editorial: bool = False,
) -> list[str]:
    sentences = split_sentences(text)
    if editorial and record is not None:
        sentences = [sentence for sentence in sentences if not sentence_is_editorial_noise(record, sentence)]
    ranked = sorted(
        enumerate(sentences),
        key=lambda item: (-sentence_score(item[1], cues, item[0]), item[0]),
    )
    picked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for idx, sentence in ranked:
        key = re.sub(r"\W+", "", sentence.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        picked.append((idx, trim_text(sentence, 360)))
        if len(picked) == limit:
            break
    picked.sort(key=lambda item: item[0])
    return [sentence for _, sentence in picked]


def build_statement_brief(record: Mapping[str, Any]) -> tuple[str, str]:
    body = strip_statement_shell(str(record.get("statement_text") or ""))
    if not body:
        fallback = f"{problem_key(record)} {record.get('title', '')}"
        return f"题面正文缺失；仅能确认题目为 {fallback}。", "题面正文缺失，无法做可靠转换。"
    sentences = split_sentences(body)
    if not sentences:
        return light_translate(body), light_translate(body)
    clean_sentences = [sentence for sentence in sentences if not sentence_is_input_noise(sentence)]
    if not clean_sentences:
        clean_sentences = sentences
    priority_sentences = []
    for index, sentence in enumerate(clean_sentences):
        lower = sentence.lower()
        has_goal = (
            "your task is" in lower
            or lower.startswith(("find ", "determine ", "count ", "construct ", "help ", "calculate "))
            or "wants to know" in lower
            or "you need to find" in lower
            or "you have to find" in lower
            or "you want to find" in lower
            or "please calculate" in lower
            or "aims to maximize" in lower
            or "aims to minimize" in lower
            or "asked you to construct" in lower
            or "would like to" in lower
            or "have to find" in lower
            or "have to deduce" in lower
            or "you should determine" in lower
            or "the task is to" in lower
        )
        if has_goal:
            priority_sentences.append((sentence_score(sentence, ("find", "determine", "count", "minimum", "maximum"), index), index, sentence))
    priority_sentences.sort(key=lambda item: (-item[0], item[1]))
    objective = [priority_sentences[0][2]] if priority_sentences else pick_top_sentences(
        body,
        ("find", "determine", "calculate", "count", "output", "construct", "minimum", "maximum", "need"),
        2,
    )
    if not objective:
        objective = sentences[:2]
    brief = " ".join(light_translate(sentence) for sentence in objective[:2])
    transformed = f"把题目先看成：{brief}"
    return trim_text(brief, 620), trim_text(transformed, 680)


def summary_piece(text: str) -> str:
    return normalize_space(text).rstrip("。；;,. ")


def build_editorial_parts(record: Mapping[str, Any]) -> tuple[list[str], str, str]:
    editorial = strip_editorial_shell(str(record.get("editorial_text") or ""))
    quality = str(record.get("editorial_quality") or "")
    if quality == "url_only" or len(editorial) < 35:
        return [], "本地题解正文不足；本条只保留题面、原题链接和题解链接，避免根据旧总结或宽标签补写。", "missing_editorial"

    observations = [summary_piece(light_translate(sentence)) for sentence in pick_top_sentences(editorial, EDITORIAL_CUES, 3, record, True)]
    solution_steps = [summary_piece(light_translate(sentence)) for sentence in pick_top_sentences(editorial, SOLUTION_CUES, 2, record, True)]
    if not observations:
        observations = [
            summary_piece(light_translate(sentence))
            for sentence in split_sentences(editorial)
            if not sentence_is_editorial_noise(record, sentence)
        ][:2]

    unique_steps: list[str] = []
    seen = set(observations)
    for step in solution_steps:
        if step not in seen:
            unique_steps.append(step)
            seen.add(step)
    key_part = "；".join(observations[:3])
    step_part = "；".join(unique_steps[:2])
    if step_part:
        solution = f"关键观察：{key_part}。做法：{step_part}。"
    else:
        solution = f"关键观察：{key_part}。按这个转换实现即可。"
    return observations, trim_text(solution, 1050), "ok"


def summary_is_ready(value: Any) -> bool:
    """Return whether a summary contains publishable content."""
    text = str(value or "").strip()
    return bool(text) and not text.startswith(SUMMARY_PLACEHOLDER_PREFIXES)


def statement_source_is_ready(record: Mapping[str, Any]) -> bool:
    """Reject records whose stored statement is missing or mirror metadata."""
    statement = str(record.get("statement_text") or "")
    if not statement.strip() or record.get("statement_quality") == "missing":
        return False
    try:
        import cf_knowledge_index as indexer

        return indexer.is_problem_statement(statement)
    except (ImportError, AttributeError):
        return len(statement.strip()) >= 80


def editorial_source_is_ready(record: Mapping[str, Any]) -> bool:
    quality = str(record.get("editorial_quality") or "")
    editorial = strip_editorial_shell(str(record.get("editorial_text") or ""))
    return quality != "url_only" and len(editorial) >= 35


def prepare_publishable_record(
    item: dict[str, Any],
    source_record: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Apply the publication gate after all manual and AI overrides."""
    if not statement_source_is_ready(source_record) or not summary_is_ready(item.get("statement_brief")):
        return None

    solution_ready = (
        summary_is_ready(item.get("solution_brief"))
        and str(item.get("extraction_status") or "") not in MISSING_SOLUTION_STATUSES
    )
    if solution_ready:
        return item

    # A missing solution summary must not leak a placeholder or a partially
    # derived explanation into the public data. The problem and statement stay
    # available so the frontend only needs a single has/no-solution state.
    item["transformed_statement"] = ""
    item["key_observations"] = []
    item["solution_brief"] = ""
    item["extraction_status"] = "missing_editorial"
    if editorial_source_is_ready(source_record):
        item["source_provenance"] = {
            **dict(item.get("source_provenance", {})),
            "editorial": "records.json:editorial_text (summary not ready; withheld)",
        }
    return item


def topic_matches(rule: TopicRule, tags: set[str], text: str) -> int:
    score = 0
    for tag in rule.tags:
        if tag in tags:
            score += 40
    lower = text.lower()
    for keyword in rule.keywords:
        if keyword in lower:
            score += 3
    return score


def classify_topics(record: Mapping[str, Any], editorial: str, statement: str) -> tuple[str, list[str]]:
    tags = {str(tag).lower() for tag in record.get("tags", [])}
    text = f"{statement} {editorial}"
    scored: list[tuple[int, int, str]] = []
    for idx, rule in enumerate(TOPIC_RULES):
        score = topic_matches(rule, tags, text)
        if score > 0:
            scored.append((score, -idx, rule.topic))
    if not scored:
        topic = "基础实现与模拟" if "implementation" in tags else "构造与贪心"
        return topic, []
    scored.sort(reverse=True)
    primary = scored[0][2]
    secondary = [topic for _, _, topic in scored[1:4] if topic != primary]
    return primary, secondary


def md_escape(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def rating_text(value: Any) -> str:
    return "未评级" if value is None else str(value)


AI_INSIGHT_FIELDS = (
    "statement_brief",
    "transformed_statement",
    "key_observations",
    "solution_brief",
    "primary_topic",
    "secondary_topics",
    "extraction_status",
)


def record_ai_input_hash(record: Mapping[str, Any]) -> str:
    payload = {
        "problem_key": problem_key(record),
        "title": record.get("title"),
        "rating": record.get("rating"),
        "problem_url": record.get("problem_url"),
        "editorial_url": record.get("editorial_url"),
        "tags": record.get("tags", []),
        "editorial_quality": record.get("editorial_quality"),
        "statement_text": record.get("statement_text") or "",
        "editorial_text": record.get("editorial_text") or "",
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_ai_overrides() -> dict[str, dict[str, Any]]:
    if not AI_GENERATED_PATH.exists():
        return {}
    raw = json.loads(AI_GENERATED_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("records"), dict):
        return {}
    return {
        str(key): entry
        for key, entry in raw["records"].items()
        if isinstance(entry, dict)
        and entry.get("status") == "ok"
        and isinstance(entry.get("insight"), dict)
    }


def apply_problem_override(item: dict[str, Any]) -> dict[str, Any]:
    override = PROBLEM_OVERRIDES.get(str(item["problem_key"]))
    if not override:
        item["manual_override"] = False
        return item
    for key, value in override.items():
        item[key] = value
    item["manual_override"] = True
    if "extraction_status" not in override:
        item["extraction_status"] = "manual_override"
    provenance = dict(item.get("source_provenance", {}))
    provenance["manual_override"] = "人工只依据 records.json 的 statement_text/editorial_text 整理"
    item["source_provenance"] = provenance
    return item


def apply_ai_override(
    item: dict[str, Any],
    raw_record: Mapping[str, Any],
    ai_overrides: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    entry = ai_overrides.get(str(item["problem_key"]))
    if not entry:
        return item
    if entry.get("input_hash") != record_ai_input_hash(raw_record):
        return item
    insight = entry.get("insight")
    if not isinstance(insight, dict):
        return item
    for key in AI_INSIGHT_FIELDS:
        if key in insight:
            item[key] = insight[key]
    item["manual_override"] = False
    item["ai_override"] = True
    provenance = dict(item.get("source_provenance", {}))
    provenance["ai_override"] = {
        "path": "ai-generated-insights.json",
        "model": entry.get("model"),
        "generated_at": entry.get("generated_at"),
        "quality_flags": insight.get("quality_flags", []),
    }
    item["source_provenance"] = provenance
    return item


def build_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    ai_overrides = load_ai_overrides()
    for ordinal, record in enumerate(records, start=1):
        statement_body = strip_statement_shell(str(record.get("statement_text") or ""))
        editorial_body = strip_editorial_shell(str(record.get("editorial_text") or ""))
        primary_topic, secondary_topics = classify_topics(record, editorial_body, statement_body)
        statement_brief, transformed_statement = build_statement_brief(record)
        key_observations, solution_brief, status = build_editorial_parts(record)
        if status == "ok":
            # Do not publish a mixed-language sentence extractor when a new
            # record has a real editorial but no validated AI summary yet.
            # The CI job must replace this placeholder before publishing.
            statement_brief = f"待生成中文题意摘要：{record.get('title') or problem_key(record)}。"
            transformed_statement = "待生成基于题解正文的核心建模与等价转化。"
            key_observations = []
            solution_brief = "待生成中文题解摘要；本地题解正文已抓取，暂不发布低质量逐词翻译。"
            status = "pending_ai"
        elif status == "missing_editorial":
            statement_brief = f"题面已抓取：{record.get('title') or problem_key(record)}；本地暂无可用题解正文。"
            transformed_statement = "本地题解正文不足，无法可靠提炼核心建模。"
        item = {
            "ordinal": ordinal,
            "problem_key": problem_key(record),
            "contest_id": record.get("contest_id"),
            "title": record.get("title"),
            "rating": record.get("rating"),
            "problem_url": record.get("problem_url"),
            "editorial_url": record.get("editorial_url"),
            "editorial_quality": record.get("editorial_quality"),
            "primary_topic": primary_topic,
            "secondary_topics": secondary_topics,
            "original_tags": record.get("tags", []),
            "statement_brief": statement_brief,
            "transformed_statement": transformed_statement,
            "key_observations": key_observations,
            "solution_brief": solution_brief,
            "extraction_status": status,
            "source_provenance": {
                "statement": "records.json:statement_text",
                "editorial": "records.json:editorial_text",
                "links_and_tags": "records.json",
            },
        }
        item = apply_problem_override(item)
        item = apply_ai_override(item, record, ai_overrides)
        publishable = prepare_publishable_record(item, record)
        if publishable is not None:
            output.append(publishable)
    return output


def write_json(records: list[dict[str, Any]], summary: Mapping[str, Any]) -> None:
    payload = {
        "generated_at": date.today().isoformat(),
        "data_sources": ["records.json"],
        "policy": {
            "only_original_scraped_problem_and_editorial_text": True,
            "discarded_previous_summary_artifacts": True,
            "notes": [
                "不读取旧分析、训练报告或人工 review 文件。",
            "若存在 ai-generated-insights.json，则只读取 input_hash 匹配的 AI 结构化摘要作为新增题目的覆写；没有通过 AI 质量校验时不发布 pending_ai 占位。",
                "题解正文缺失时不补写旧总结，只标记为本地题解正文不足。",
                "题面总结未就绪的记录不进入发布数据；题解总结未就绪时仅发布题面，题解相关字段全部留空。",
                "分类使用 records.json 中的原始 Codeforces tags，并辅以原题解/题面正文关键词。",
            ],
        },
        "summary": dict(summary),
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def problem_entry_md(item: Mapping[str, Any]) -> list[str]:
    tags = ", ".join(str(tag) for tag in item.get("original_tags", [])) or "无"
    secondary = " / ".join(str(topic) for topic in item.get("secondary_topics", [])) or "无"
    lines = [
        f"### {item['problem_key']} {item['title']}（{rating_text(item.get('rating'))}）",
        "",
        f"- 原题：{item['problem_url']}",
        f"- 题解：{item['editorial_url']}",
        f"- 分类：{item['primary_topic']}；次级：{secondary}；原始标签：{tags}",
        f"- 题意：{item['statement_brief']}",
    ]
    if item.get("solution_brief"):
        lines.extend(
            [
                f"- 转换：{item['transformed_statement']}",
                f"- 题解：{item['solution_brief']}",
            ]
        )
    lines.append("")
    return lines


def write_by_problem(records: list[dict[str, Any]], summary: Mapping[str, Any]) -> None:
    lines = [
        "# CF 题意与题解关键观察索引（按题目）",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "内容只来自 `records.json` 中抓取到的原题面和原题解正文；不使用旧分析、训练报告或 review 总结产物。",
        "",
        "## 汇总",
        "",
        f"- 扫描题目数：{summary['total_problems']}",
        f"- 有本地题解正文的题目数：{summary['with_editorial_brief']}",
        f"- 本地题解正文不足的题目数：{summary['missing_editorial_brief']}",
        f"- 大知识点数量：{summary['primary_topic_count']}",
        "",
        "## 全量题目",
        "",
    ]
    for item in records:
        lines.extend(problem_entry_md(item))
    OUT_BY_PROBLEM.write_text("\n".join(lines), encoding="utf-8")


def write_by_topic(records: list[dict[str, Any]], summary: Mapping[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        grouped[str(item["primary_topic"])].append(item)

    lines = [
        "# CF 题意与题解关键观察索引（按大知识点）",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "每题只归入一个主知识点，次级知识点保留在题目条目中。内容来源限定为抓取到的原题面和原题解正文。",
        "",
        "## 汇总",
        "",
        f"- 扫描题目数：{summary['total_problems']}",
        f"- 有本地题解正文的题目数：{summary['with_editorial_brief']}",
        f"- 本地题解正文不足的题目数：{summary['missing_editorial_brief']}",
        "",
    ]
    for topic in TOPIC_ORDER:
        items = grouped.get(topic, [])
        if not items:
            continue
        lines.extend([f"## {topic}", "", f"题目数：{len(items)}", ""])
        for item in sorted(items, key=lambda row: (int(row["contest_id"]) if "contest_id" in row else 0, str(row["problem_key"]))):
            lines.extend(problem_entry_md(item))
    OUT_BY_TOPIC.write_text("\n".join(lines), encoding="utf-8")


def joined_public_text(item: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in ("statement_brief", "transformed_statement", "solution_brief")
    )


def english_word_count(text: str) -> int:
    words = re.findall(r"\b[A-Za-z][A-Za-z-]{3,}\b", text)
    return sum(1 for word in words if word.lower() not in ENGLISH_ALLOWED_WORDS)


def top_noise_rows(records: list[dict[str, Any]], limit: int = 12) -> list[tuple[int, str, str, str]]:
    rows = [
        (
            english_word_count(joined_public_text(item)),
            str(item["problem_key"]),
            str(item["title"]),
            trim_text(joined_public_text(item), 180),
        )
        for item in records
    ]
    return [row for row in sorted(rows, reverse=True)[:limit] if row[0] > 0]


def write_quality(records: list[dict[str, Any]], summary: Mapping[str, Any]) -> None:
    empty_statement = [item["problem_key"] for item in records if not item.get("statement_brief")]
    empty_solution = [item["problem_key"] for item in records if not item.get("solution_brief")]
    sample = records[:20]
    sample_missing = [
        item["problem_key"]
        for item in sample
        if not item.get("statement_brief") or not item.get("solution_brief") or not item.get("problem_url") or not item.get("editorial_url")
    ]
    shell_hits = [str(item["problem_key"]) for item in records if STORY_OR_SHELL_PATTERN.search(joined_public_text(item))]
    markup_hits = [str(item["problem_key"]) for item in records if "Unable to parse markup" in joined_public_text(item)]
    noisy_rows = top_noise_rows(records)
    topics = Counter(str(item["primary_topic"]) for item in records)
    lines = [
        "# CF 题意与题解关键观察索引质量检查",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "## 来源约束",
        "",
        "- 实际读取数据源：`records.json`",
        "- 未读取旧总结产物：旧分析、训练报告和 review 文件",
        "- 题解缺正文时不补写，只标记为本地题解正文不足。",
        "",
        "## 统计",
        "",
        f"- 扫描题目总数：{summary['total_problems']}",
        f"- 有题面简述的题目数：{summary['with_statement_brief']}",
        f"- 有本地题解正文并生成题解简述的题目数：{summary['with_editorial_brief']}",
        f"- 有可用题解简述的题目数：{summary['with_solution_brief']}",
        f"- 本地题解正文不足的题目数：{summary['missing_editorial_brief']}",
        f"- 基于题面结构补出简要题解的题目数：{summary['statement_derived_solution']}",
        f"- 问题级人工覆写数量：{summary['manual_override_count']}",
        f"- 大知识点数量：{summary['primary_topic_count']}",
        "",
        "## 大知识点分布",
        "",
    ]
    for topic, count in topics.most_common():
        lines.append(f"- {topic}：{count}")
    lines.extend(
        [
            "",
            "## 完整性检查",
            "",
            f"- statement_brief 空值数量：{len(empty_statement)}",
            f"- solution_brief 空值数量：{len(empty_solution)}",
            f"- 抽样 20 条链接/题意/题解字段缺失数量：{len(sample_missing)}",
            f"- 故事壳/输入输出/投票噪音命中数量：{len(shell_hits)}",
            f"- `Unable to parse markup` 残留数量：{len(markup_hits)}",
            f"- 英文残留 top 样本数量：{len(noisy_rows)}",
        ]
    )
    if sample_missing:
        lines.append("- 抽样缺失题目：" + ", ".join(sample_missing))
    else:
        lines.append("- 抽样结果：前 20 条均有链接、题意和题解字段。")
    if shell_hits:
        lines.append("- 噪音命中样本：" + ", ".join(shell_hits[:20]))
    if markup_hits:
        lines.append("- markup 残留题目：" + ", ".join(markup_hits[:20]))
    if noisy_rows:
        lines.extend(["", "## 英文残留 Top 样本", ""])
        for count, key, title, excerpt in noisy_rows:
            lines.append(f"- {key} {title}：{count} 个英文词；{excerpt}")
    lines.extend(
        [
            "",
            "## 剩余风险",
            "",
            "- 这是抽取式/轻量改写版，不是逐题人工精修；少数题的题意或题解句子可能仍偏原文。",
            "- URL-only 或题解正文过短的题无法从本地原题解提炼关键观察。",
            "- 分类依赖原始 CF tags 和正文关键词，可能与个人训练体系的大类边界不完全一致。",
        ]
    )
    OUT_QUALITY.write_text("\n".join(lines), encoding="utf-8")


def summarize(records: list[dict[str, Any]], source_total: int | None = None) -> dict[str, Any]:
    missing_statuses = {"missing_editorial", "statement_only_missing_editorial", "pending_ai"}
    editorial_statuses = {
        "ok",
        "manual_override",
        "ai_generated_with_editorial",
        "ai_generated_partial_editorial",
    }
    return {
        "total_problems": len(records),
        "source_total_problems": len(records) if source_total is None else source_total,
        "filtered_out_problems": max(0, (len(records) if source_total is None else source_total) - len(records)),
        "with_statement_brief": sum(1 for item in records if item.get("statement_brief")),
        "with_editorial_brief": sum(1 for item in records if item.get("extraction_status") in editorial_statuses),
        "with_solution_brief": sum(1 for item in records if item.get("solution_brief")),
        "missing_editorial_brief": sum(1 for item in records if item.get("extraction_status") in missing_statuses),
        "statement_derived_solution": sum(1 for item in records if item.get("extraction_status") == "statement_derived"),
        "manual_override_count": sum(1 for item in records if item.get("manual_override")),
        "ai_override_count": sum(1 for item in records if item.get("ai_override")),
        "primary_topic_count": len({item["primary_topic"] for item in records}),
    }


def main() -> None:
    raw_records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_records, list):
        raise TypeError("records.json must contain a list")
    records = build_records(raw_records)
    summary = summarize(records, source_total=len(raw_records))
    write_json(records, summary)
    write_by_problem(records, summary)
    write_by_topic(records, summary)
    write_quality(records, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
