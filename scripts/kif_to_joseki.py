#!/usr/bin/env python3
"""ShogiGUI で作った定跡の KIF（joseki/*.kif）を、web/nakabisha.html の定跡データに変換する。

  python3 scripts/kif_to_joseki.py          # web/nakabisha.html の生成部分を書き直す
  python3 scripts/kif_to_joseki.py --check  # 生成部分が最新か確かめるだけ（テストで使う）

コースの一覧は joseki/courses.json。KIF の読み方
  - 本線と「変化：N手」の分岐を木にする。分岐は相手の手で作る（自分の手の分岐は「有力」な別の手として扱う）
  - コメント（* の行）：ふつうの文＝その手の意味、「ヒント:」＝考え方のヒント、
    「悪手 ▲7六歩:」＝よくある間違いとその理由、「有力 ▲2六歩:」＝同じくらい良い手、「分岐:」＝分岐の名前。
    初手より前のコメントはコースの説明（intro）になる。「*一致率」は ShogiGUI が付ける行なので読まない
  - 棋譜解析（**解析 の行）：評価値と読み筋を EV（評価値データ）にする。評価値は先手から見た値として読む
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOSEKI = os.path.join(ROOT, "joseki")
HTML = os.path.join(ROOT, "web", "nakabisha.html")
BEGIN = "/*KIF_JOSEKI_BEGIN（scripts/kif_to_joseki.py が joseki/ から生成。手で直さない）*/"
END = "/*KIF_JOSEKI_END*/"
ANCHOR = "\nlet leafCount=0;\n"  # 定跡ツリーを組み立てる直前に差し込む
PV_MAX = 8

ZEN = "０１２３４５６７８９"
KAN = "〇一二三四五六七八九"
PIECE = {"歩": "P", "香": "L", "桂": "N", "銀": "S", "金": "G", "角": "B", "飛": "R", "玉": "K", "王": "K"}
PROMOTED = {"と": "P", "成香": "L", "杏": "L", "成桂": "N", "圭": "N", "成銀": "S", "全": "S", "馬": "B", "龍": "R", "竜": "R"}
MOVE_RE = re.compile(r"^(?:([１-９1-9])([一二三四五六七八九1-9])|同　?)(成香|成桂|成銀|[歩香桂銀金角飛玉王と杏圭全馬龍竜])(不成|成)?(打)?(?:\((\d\d)\))?")


def die(msg):
    sys.exit("kif_to_joseki: " + msg)


def digit(c):
    if c in ZEN:
        return str(ZEN.index(c))
    if c in KAN:
        return str(KAN.index(c))
    return c


# ---------- 盤面（コメント中の「▲7六歩」を指し手に直すためだけの最小限） ----------

def initial():
    b = {}
    back = "LNSGKGSNL"
    for f in range(1, 10):
        b[f"{f}9"] = (back[f - 1], 0, False)
        b[f"{f}7"] = ("P", 0, False)
        b[f"{f}1"] = (back[f - 1], 1, False)
        b[f"{f}3"] = ("P", 1, False)
    b["88"] = ("B", 0, False)
    b["28"] = ("R", 0, False)
    b["82"] = ("R", 1, False)
    b["22"] = ("B", 1, False)
    return b


def play(b, m, side):
    b = dict(b)
    if m[1] == "*":
        b[m[2:4]] = (m[0], side, False)
    else:
        t, s, p = b.pop(m[:2])
        b[m[2:4]] = (t, s, p or m.endswith("+"))
    return b


GOLD = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (0, 1)]
STEP = {"K": [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)], "G": GOLD,
        "S": [(-1, -1), (0, -1), (1, -1), (-1, 1), (1, 1)], "N": [(-1, -2), (1, -2)], "P": [(0, -1)]}
SLIDE = {"B": [(-1, -1), (1, -1), (-1, 1), (1, 1)], "R": [(0, -1), (0, 1), (-1, 0), (1, 0)], "L": [(0, -1)]}


def reaches(b, frm, to):
    t, s, p = b[frm]
    d = -1 if s else 1  # 先手は段の数字が小さくなる向きが前
    f, r = int(frm[0]), int(frm[1])
    tf, tr = int(to[0]), int(to[1])
    steps = GOLD if p and t in "PLNS" else STEP.get(t, [])
    if p and t == "B":
        steps = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    if p and t == "R":
        steps = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for df, dr in steps:
        if (f + df * d, r + dr * d) == (tf, tr):
            return True
    for df, dr in SLIDE.get(t, []) if not (p and t == "L") else []:
        nf, nr = f, r
        while True:
            nf += df * d
            nr += dr * d
            if not (1 <= nf <= 9 and 1 <= nr <= 9):
                break
            if (nf, nr) == (tf, tr):
                return True
            if f"{nf}{nr}" in b:
                break
    return False


def resolve(b, side, text, where):
    """コメント中の「▲7六歩」「△2二角成」「▲5五角打」「▲5六銀(57)」を指し手に直す"""
    m = re.match(r"^[▲△☗☖]?\s*([１-９1-9])([一二三四五六七八九1-9])(成香|成桂|成銀|[歩香桂銀金角飛玉王と杏圭全馬龍竜])(不成|成)?(打)?(?:\((\d\d)\))?$", text.strip())
    if not m:
        die(f"{where}: 手の書き方が読めません「{text}」（例：▲7六歩、△2二角成、▲5五角打、▲5六銀(57)）")
    to = digit(m.group(1)) + digit(m.group(2))
    name, promo, drop, frm = m.group(3), m.group(4) == "成", m.group(5), m.group(6)
    promoted = name in PROMOTED
    t = PROMOTED.get(name) or PIECE[name]
    if drop:
        return f"{t}*{to}"
    cands = [frm] if frm else [k for k, (pt, ps, pp) in b.items()
                               if ps == side and pt == t and pp == promoted and k != to and reaches(b, k, to)]
    if len(cands) != 1:
        die(f"{where}: 「{text}」に当てはまる駒が{len(cands)}枚あります。▲5六銀(57) のように元の位置を書いてください")
    return cands[0] + to + ("+" if promo else "")


# ---------- KIF の読み込み ----------

def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    die(f"{path}: 文字コードが読めません")


class Node:
    def __init__(self, parent, m=None, label=""):
        self.parent, self.m, self.label = parent, m, label
        self.kids, self.comments, self.runs = [], [], []
        self.depth = parent.depth + 1 if parent else 0
        self.to = m[2:4] if m else None

    def path(self):
        ms = []
        n = self
        while n.m:
            ms.append(n.m)
            n = n.parent
        return " ".join(reversed(ms))


def parse_move(tok, prev_to, where):
    m = MOVE_RE.match(tok)
    if not m:
        die(f"{where}: 指し手が読めません「{tok}」")
    to = digit(m.group(1)) + digit(m.group(2)) if m.group(1) else prev_to
    if not to:
        die(f"{where}: 「同」の前に手がありません")
    name, promo, drop, frm = m.group(3), m.group(4) == "成", m.group(5), m.group(6)
    if drop:
        return f"{PIECE[name]}*{to}"
    if not frm:
        die(f"{where}: 元の位置 (xx) がない指し手です「{tok}」")
    return frm + to + ("+" if promo else "")


def parse_pv(text, prev_to):
    moves = []
    for tok in text.split(" "):  # 「同　飛」の全角空白で分けない
        if not tok:
            continue
        tok = tok.lstrip("▲△☗☖")
        if not MOVE_RE.match(tok):
            break  # 投了など
        mv = parse_move(tok, prev_to, "読み筋")
        moves.append(mv)
        prev_to = mv[2:4]
        if len(moves) >= PV_MAX + 1:
            break
    return moves


def parse_kif(path):
    lines = read_text(path).replace("\r", "").split("\n")
    root = Node(None)
    seqs = [(1, [root])]  # (最初の手数, [その手数の直前の局面, 1手指した局面, ...])
    cur = root
    nodes = seqs[0][1]
    for i, line in enumerate(lines, 1):
        where = f"{os.path.basename(path)} {i}行目"
        if line.startswith("変化："):
            n = int(re.search(r"\d+", line).group())
            for start, ns in reversed(seqs):
                if start <= n <= start + len(ns) - 1:
                    base = ns[n - start]
                    break
            else:
                die(f"{where}: {n}手目の分岐元が見つかりません")
            nodes = [base]
            seqs.append((n, nodes))
            cur = base
            continue
        mm = re.match(r"^ *(\d+) +(.+)$", line)
        if mm:
            tok = re.sub(r" *\( *\d+:\d+.*$", "", mm.group(2)).strip()  # 消費時間を外す
            if tok.startswith(("投了", "中断", "詰み", "千日手", "持将棋")):
                continue
            mv = parse_move(tok, cur.to, where)
            side = (int(mm.group(1)) - 1) % 2
            child = next((k for k in cur.kids if k.m == mv), None)
            if not child:
                child = Node(cur, mv, ("▲" if side == 0 else "△") + tok.split("(")[0].replace("　", ""))
                cur.kids.append(child)
            cur = child
            nodes.append(cur)
        elif line.startswith("**解析"):
            mt = re.search(r"候補(\d+).*?評価値 (\S+)(?: (\d+))?.*?読み筋 (.*)$", line)
            if not mt:
                continue
            k, val, mate, pv = int(mt.group(1)), mt.group(2), mt.group(3), mt.group(4)
            if "詰" in val:
                v = (30000 - int(mate or 0)) * (-1 if val.startswith("-") else 1)
            else:
                v = int(re.sub(r"[^-+0-9]", "", val))  # 「-72↑」のような上限・下限の印は外す
            moves = parse_pv(pv, cur.to)
            if not moves:
                continue
            if k == 1 or not cur.runs:
                cur.runs.append([])
            cur.runs[-1].append((v, moves))
        elif line.startswith("*") and not line.startswith("**"):
            text = line[1:].strip()
            if text and not text.startswith("一致率"):
                cur.comments.append(text)
    return root


# ---------- コースのデータへの変換 ----------

def classify(node, side, where):
    """コメントを c（意味）・h（ヒント）・w（悪手）・ok（有力）・branch（分岐名）に分ける"""
    out = {"c": [], "h": [], "w": {}, "ok": {}, "branch": None}
    parent_pos = None
    for text in node.comments:
        if re.match(r"^分岐名?[:：]", text):
            out["branch"] = re.sub(r"^分岐名?[:：]\s*", "", text)
        elif re.match(r"^ヒント[:：]", text):
            out["h"].append(re.sub(r"^ヒント[:：]\s*", "", text))
        elif re.match(r"^(悪手|有力)\s", text):
            kind, rest = text.split(None, 1)
            mv_text, _, reason = re.split(r"([:：])", rest, maxsplit=1)
            if parent_pos is None:
                parent_pos = board_at(node.parent)
            mv = resolve(parent_pos, side, mv_text, where)
            out["w" if kind == "悪手" else "ok"][mv] = reason.strip()
        else:
            out["c"].append(text)
    return out


def board_at(node):
    ms = []
    n = node
    while n.m:
        ms.append(n.m)
        n = n.parent
    b = initial()
    for i, m in enumerate(reversed(ms)):
        b = play(b, m, i % 2)
    return b


def step(node, user):
    side = (node.depth - 1) % 2
    cl = classify(node, side, f"{node.label}（{node.path()}）")
    st = {"m": node.m, "c": "".join(cl["c"])}
    if side == user:
        st.update(h="".join(cl["h"]), w=cl["w"], ok=cl["ok"])
    return st, cl["branch"]


def build_seq(node, user, warn):
    """node の子から先を、LINES の seq の形にする"""
    seq = []
    while node.kids:
        kids = node.kids
        side = node.depth % 2
        if len(kids) > 1 and side == user:
            # 自分の手の分岐：最初の手を正解にし、ほかは「有力な手」として残す（その先の手順は使わない）
            main, rest = kids[0], kids[1:]
            st, _ = step(main, user)
            for k in rest:
                cl = classify(k, side, k.label)
                st["ok"].setdefault(k.m, "".join(cl["c"]) or "同じくらい有力な手です。")
                warn.append(f"{k.label}（{k.path()}）：自分の手の分岐なので「有力な手」として扱い、その先の手順は使いません")
            seq.append(st)
            node = main
            continue
        if len(kids) > 1:
            br = []
            for k in kids:
                st, name = step(k, user)
                br.append({"name": name or k.label, "seq": [st] + build_seq(k, user, warn)})
            seq.append({"br": br})
            return seq
        st, _ = step(kids[0], user)
        seq.append(st)
        node = kids[0]
    return seq


def ev_records(root):
    ev = {}

    def walk(n):
        if n.runs:
            run = n.runs[-1]
            t = n.depth % 2  # 手番
            top = []
            for v, moves in run:
                vv = v if t == 0 else -v  # 先手から見た値 → 手番から見た値
                top.append([moves[0], vv, moves[1:PV_MAX + 1]])
            top.sort(key=lambda x: -x[1])
            ev[n.path()] = {"t": t, "top": top[:5], "all": {m: [v, pv] for m, v, pv in top}}
        for k in n.kids:
            walk(k)

    walk(root)
    return ev


def generate():
    conf = json.load(open(os.path.join(JOSEKI, "courses.json"), encoding="utf-8"))
    lines, ev, warn = [], {}, []
    for c in conf:
        root = parse_kif(os.path.join(JOSEKI, c["file"]))
        user = c["side"]
        intro = "".join(root.comments) or c.get("intro", "")
        lines.append({"id": c["id"], "title": c["title"], "sub": c["sub"], "side": user, "kif": True,
                      "intro": intro, "seq": build_seq(root, user, warn)})
        for k, v in ev_records(root).items():
            ev.setdefault(k, v)
    js = (BEGIN + "\n"
          + "LINES.push(..." + json.dumps(lines, ensure_ascii=False, separators=(",", ":")) + ");\n"
          + "{const KEV=" + json.dumps(ev, ensure_ascii=False, separators=(",", ":"))
          + ";for(const k in KEV)if(!EV[k])EV[k]=KEV[k];}\n"
          + END)
    return js, warn


def main():
    html = open(HTML, encoding="utf-8").read()
    js, warn = generate()
    if BEGIN in html:
        a = html.index(BEGIN)
        b = html.index(END) + len(END)
        new = html[:a] + js + html[b:]
    else:
        if html.count(ANCHOR) != 1:
            die("差し込む場所（let leafCount=0;）が見つかりません")
        new = html.replace(ANCHOR, "\n" + js + ANCHOR)
    for w in warn:
        print("注意:", w)
    if "--check" in sys.argv[1:]:
        if new != html:
            sys.exit("web/nakabisha.html の定跡データが古いままです。python3 scripts/kif_to_joseki.py を実行してください")
        print("web/nakabisha.html is up to date")
        return
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(new)
    print("wrote", os.path.relpath(HTML, ROOT))


if __name__ == "__main__":
    main()
