# -*- coding: utf-8 -*-
"""AIM 2627 Python Coursework —— 哨兵 Sentry 控制模块（学生骨架）。

你的全部作业都在本文件里：按题面（题面.pdf）各题的规范补全每个标有 TODO 的函数。
- 骨架已提供：Facing / SentryState 枚举、SentryGrid 的构造与只读属性、
  渲染函数 render_frame（demo 用，不进测试）。
- 你要实现：Q1-Q6 与 Bonus 的全部 TODO，以及 SentryGrid 的
  四个方法（current_pos 的 setter、move_forward、turn_left、turn_right）。
- 未实现的函数 raise NotImplementedError：可见测试会自动 skip，
  CI 一开始就是绿的；实现一个，对应测试亮一个。
- `python main.py`（或 PYTHONPATH=src python -m main）可看 ASCII 演示。
"""
import json
from enum import Enum


# ---------------------------------------------------------------------------
# 仿真世界基础（已提供，勿改）
# ---------------------------------------------------------------------------
class Facing(Enum):
    """朝向枚举。世界坐标 (x, y)：x 向右增长，y 向上增长（数学系）。"""

    UP = (0, 1)
    DOWN = (0, -1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def delta(self):
        """该朝向的单位位移向量 (dx, dy)。"""
        return self.value[0], self.value[1]


# ---------------------------------------------------------------------------
# Q1 机器人自检（题面 Q1·自检状态计算与报告生成）
# ---------------------------------------------------------------------------
def hp_ratio(hp, max_hp):
    if max_hp <= 0:
        return 0
    ratio = (hp * 100) / max_hp
    return int(max(0, min(100, round(ratio))))


def status_report(name, robot_type, hp, max_hp, battery):
    hp_pct = hp_ratio(hp, max_hp)
    if battery < 20:
        battery_status = "LOW"
    elif battery < 60:
        battery_status = "WARNING"
    else:
        battery_status = "OK"
    return (f"{name:<10}| {robot_type} |HP {hp_pct:>3}%|"
            f"BAT {battery:>3}%|{battery_status}")

# ---------------------------------------------------------------------------
# Q2 战斗日志分析（题面 Q2·多源日志解析与统计）
# ---------------------------------------------------------------------------
import json

def analyze_damage_log(lines):

    # 初始化统计变量
    total = 0
    by_armor = {"front": 0, "left": 0, "right": 0}
    seen_ids = set()  #记录已经出现过的id，避免重复计数
    event_count = 0   #记录有效事件的数量
    sensor_armor = {"F": "front", "L": "left", "R": "right"}

    def reject_json_constant(value):
        raise ValueError(value)

    try:
        line_iterator = iter(lines)
    except Exception:
        line_iterator = iter(())

    while True:
        try:
            raw_line = next(line_iterator)
        except StopIteration:
            break
        except Exception:
            break

        if not isinstance(raw_line, str):
            continue
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

    # 处理 JSON 格式的行
        if line.startswith("{"):
            try:
                data = json.loads(line, parse_constant=reject_json_constant)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            armor = data.get("armor")
            damage = data.get("damage")
            if (not isinstance(armor, str) or armor not in by_armor
                    or type(damage) is not int or damage <= 0):
                continue

            if "id" in data:
                try:
                    id_key = json.dumps(
                        data["id"], sort_keys=True, separators=(",", ":"),
                        allow_nan=False,
                    )
                except Exception:
                    continue
                if id_key in seen_ids:
                    continue
                seen_ids.add(id_key)

            total += damage
            by_armor[armor] += damage
            event_count += 1
            continue

        temp_events = []
        is_valid_line = True

        # 处理传感器格式的行
        for part in line.split(","):
            if part.count(":") != 1:
                is_valid_line = False
                break
            key, value = (field.strip() for field in part.split(":"))
            if (key not in sensor_armor or not value.isascii()
                    or not value.isdecimal()):
                is_valid_line = False
                break
            try:
                damage = int(value)
            except (ValueError, OverflowError):
                is_valid_line = False
                break
            if damage <= 0:
                is_valid_line = False
                break
            temp_events.append((sensor_armor[key], damage))

        if not is_valid_line or not temp_events:
            continue
        for armor, damage in temp_events:
            total += damage
            by_armor[armor] += damage
            event_count += 1

    # 计算最终结果
    if event_count == 0:
        most_hit = None
        avg = 0.0
    else:
        most_hit = max(by_armor, key=by_armor.get)
        avg = round(total / event_count, 2)

    return {
        "total": total,
        "by_armor": by_armor,
        "most_hit": most_hit,
        "avg": avg,
    }


# ---------------------------------------------------------------------------
# Q3 SentryGrid（题面 Q3·载体物理规则）
# ---------------------------------------------------------------------------
class SentryGrid:

    def __init__(self, width, height, obstacles, enemy_pos,
                 start_pos=(0, 0), facing=Facing.UP, fuel=100):
        self._width = int(width)
        self._height = int(height)
        if self._width <= 0 or self._height <= 0:
            raise ValueError("地图尺寸必须为正")
        # 障碍坐标存入 set，查询 O(1)
        self._obstacles = set()
        for ob in obstacles:
            x, y = ob
            self._obstacles.add((int(x), int(y)))
        if not isinstance(enemy_pos, (tuple, list)) or len(enemy_pos) != 2:
            raise TypeError("enemy_pos 需要长度为 2 的 tuple/list")
        self._enemy_pos = self._clamp_cell(enemy_pos)
        if self._enemy_pos in self._obstacles:
            raise ValueError("enemy_pos 不能位于障碍物上")
        if not isinstance(facing, Facing):
            facing = Facing.UP
        self._facing = facing
        self._fuel = int(fuel)
        self._collision_count = 0
        self._pos = self._clamp_cell(start_pos)
        if self._pos in self._obstacles:
            raise ValueError("start_pos 不能位于障碍物上")

    def _clamp_cell(self, cell):
        """已提供：元素转 int 并夹回地图范围（供 __init__ 使用）。"""
        x = int(cell[0])
        y = int(cell[1])
        x = max(0, min(self._width - 1, x))
        y = max(0, min(self._height - 1, y))
        return (x, y)

    # -- 只读属性（已提供，勿改） ------------------------------------------
    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def enemy_pos(self):
        return self._enemy_pos

    @property
    def facing(self):
        return self._facing

    @property
    def fuel(self):
        return self._fuel

    @property
    def collision_count(self):
        return self._collision_count

    @property
    def obstacles(self):
        """障碍集合的只读视图（内部 set 引用，不要修改它）。"""
        return self._obstacles

    @property
    def found_enemy(self):
        return self._pos == self._enemy_pos

    def is_blocked(self, x, y):
        """已提供：坐标是否为障碍或越界（O(1)）。"""
        return ((x, y) in self._obstacles
                or not (0 <= x < self._width and 0 <= y < self._height))

    # -- 你要实现的部分 ------------------------------------------------------
    @property
    def current_pos(self):
        """当前位置 (x, y) 的 tuple。"""
        return self._pos

    @current_pos.setter
    def current_pos(self, value):
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise TypeError("current_pos 需要长度为 2 的 tuple/list")
        x = int(value[0])
        y = int(value[1])
        if not (0 <= x < self._width and 0 <= y < self._height):
            raise ValueError("current_pos 越界")
        if (x, y) in self._obstacles:
            raise ValueError("current_pos 不能位于障碍物上")
        self._pos = (x, y)

    def move_forward(self):
        if self._fuel <= 0:
            return self._pos

        dx, dy = self._facing.delta
        nx = self._pos[0] + dx
        ny = self._pos[1] + dy

        if self.is_blocked(nx, ny):
            self._collision_count += 1
            return self._pos

        self._pos = (nx, ny)
        self._fuel -= 1
        return self._pos

    def turn_left(self):
        """原地左转 90°,返回新的 Facing(不耗电)。"""
        order = [Facing.UP, Facing.LEFT, Facing.DOWN, Facing.RIGHT]
        idx = order.index(self._facing)
        self._facing = order[(idx + 1) % 4]
        return self._facing

    def turn_right(self):
        """原地右转 90°,返回新的 Facing(不耗电)。"""
        order = [Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT]
        idx = order.index(self._facing)
        self._facing = order[(idx + 1) % 4]
        return self._facing


# ---------------------------------------------------------------------------
# Q4 贪心导航（题面 Q4·单步贪心导航策略）
# ---------------------------------------------------------------------------
def next_step_toward(pos, target, obstacles, current_facing=Facing.UP):
    """返回下一步应朝向的 Facing。"""
    if pos == target:
        return current_facing

    x, y = pos
    tx, ty = target
    obstacles = set(obstacles)

    def is_valid(direction):
        nx = x + direction.delta[0]
        ny = y + direction.delta[1]
        if (nx, ny) in obstacles:
            return False
        return abs(nx - tx) + abs(ny - ty) < abs(x - tx) + abs(y - ty)

    if abs(tx - x) >= abs(ty - y):
        priority = [
            Facing.RIGHT if tx > x else Facing.LEFT,
            Facing.UP if ty > y else Facing.DOWN,
        ]
    else:
        priority = [
            Facing.UP if ty > y else Facing.DOWN,
            Facing.RIGHT if tx > x else Facing.LEFT,
        ]

    for direction in priority:
        if is_valid(direction):
            return direction

    for direction in [Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT]:
        if is_valid(direction):
            return direction

    return current_facing


# ---------------------------------------------------------------------------
# Q5 哨兵决策机（题面 Q5·裁判系统决策规则表）
# ---------------------------------------------------------------------------
class SentryState(Enum):
    """哨兵状态机（已提供，勿改）。"""

    PATROL = "PATROL"
    SUSPECT = "SUSPECT"
    ENGAGE = "ENGAGE"
    RETREAT = "RETREAT"
    RETURN = "RETURN"


def decide(sensor, state, hp, heat):

    #非法输入检查
    if not isinstance(sensor, dict):
        raise TypeError("sensor 必须是字典")
    for key in ["enemy_frames", "enemy_dist", "robot_type", "max_hp"]:
        if key not in sensor:
            raise KeyError(f"sensor 缺少键 {key}")

    enemy_frames = sensor["enemy_frames"]
    if not isinstance(enemy_frames, (tuple, list)) or len(enemy_frames) == 0 or len(enemy_frames) > 6:
        raise ValueError("enemy_frames 必须为长度1-6的序列")
    if not isinstance(state, SentryState):
        raise ValueError("state 必须是 SentryState 成员")

    #输入规范化
    frames = [bool(x) for x in enemy_frames]
    visible = frames[-1] 

    enemy_dist = sensor.get("enemy_dist")
    if not isinstance(enemy_dist, int) or isinstance(enemy_dist, bool):
        enemy_dist = 9999

    robot_type = sensor.get("robot_type")
    if robot_type not in ("INFANTRY", "HERO"):
        robot_type = "INFANTRY"

    max_hp = sensor.get("max_hp")
    if not isinstance(max_hp, int) or max_hp <= 0:
        max_hp = 100
    hp_pct = (hp * 100) // max_hp
    hp_pct = max(0, min(100, hp_pct))

    #规则 R1-R7
    if hp_pct <= 30:
        return ("RETREAT", SentryState.RETREAT)
    if state == SentryState.RETREAT:
        if hp_pct > 30:
            return ("RETURN", SentryState.RETURN)
        else:
            return ("RETREAT", SentryState.RETREAT)
    if state == SentryState.RETURN:
        return ("MOVE_BASE", SentryState.PATROL)
    if state == SentryState.ENGAGE and visible:
        if enemy_dist <= 3:
            return ("SHOOT", SentryState.ENGAGE)
        else:
            if robot_type == "HERO":
                return ("MOVE_RIGHT", SentryState.ENGAGE)
            else:
                return ("MOVE_LEFT", SentryState.ENGAGE)
    if state == SentryState.ENGAGE and not visible:
        if any(frames):
            return ("HOLD_FIRE", SentryState.ENGAGE)
        else:
            return ("SCAN", SentryState.SUSPECT)
    if state in (SentryState.PATROL, SentryState.SUSPECT) and visible:
        if len(frames) >= 2 and frames[-1] and frames[-2]:
            if enemy_dist <= 3:
                return ("SHOOT", SentryState.ENGAGE)
            else:
                if robot_type == "HERO":
                    return ("MOVE_RIGHT", SentryState.ENGAGE)
                else:
                    return ("MOVE_LEFT", SentryState.ENGAGE)
        else:
            return ("SCAN", SentryState.SUSPECT)
    if state in (SentryState.PATROL, SentryState.SUSPECT) and not visible:
        if state == SentryState.PATROL:
            return ("PATROL_MOVE", SentryState.PATROL)
        else:
            return ("SCAN", SentryState.SUSPECT)

    return ("SCAN", SentryState.SUSPECT)


# ---------------------------------------------------------------------------
# Q6 巡逻任务（题面 Q6·巡逻契约与验收阈值）
# ---------------------------------------------------------------------------
def run_patrol(grid, max_steps=500):
    """TODO(Q6)：sense → decide → act 主循环；
    循环结构、终止条件、脱困自由度与统计返回契约见题面 Q6 规范。"""
    raise NotImplementedError("Q6 run_patrol：题面 Q6·主循环与统计契约")


def report_to_json(stats):
    """TODO(Q6)：把 stats 序列化为确定性的 JSON 字符串，见题面 Q6 规范。"""
    raise NotImplementedError("Q6 report_to_json：题面 Q6·报告序列化")


# ---------------------------------------------------------------------------
# Bonus：BFS 全局最短路（题面 Bonus·BFS 语义与排行榜）
# ---------------------------------------------------------------------------
def bfs_path_length(start, target, obstacles):
    """TODO(Bonus)：BFS 全局最短路步数；返回语义与边界职责见题面 Bonus 规范。"""
    raise NotImplementedError("Bonus bfs_path_length")


# ---------------------------------------------------------------------------
# 渲染（已提供，demo 专用，不进测试）
# ---------------------------------------------------------------------------
def render_frame(grid, trail=()):
    """ASCII 渲染一帧战场；trail 为走过的格子集合。返回 list[str]。"""
    trail = set(trail)
    rows = []
    for y in range(grid.height - 1, -1, -1):
        row = []
        for x in range(grid.width):
            if (x, y) == grid.current_pos:
                row.append("◉")
            elif (x, y) == grid.enemy_pos:
                row.append("▲")
            elif (x, y) in grid.obstacles:
                row.append("█")
            elif (x, y) in trail:
                row.append("·")
            else:
                row.append(".")
        rows.append("".join(row))
    return rows
