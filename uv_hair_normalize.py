# 使用方式：UV编辑器顶部菜单 / 搜索命令（F3）：一键发丝UV长条拉直规整
# 目标：预先选中连续 UV 长条的左右两条长边（不含顶底边），执行后
# 将整个 UV 拉成规则的方形长条，像梯子一样：
# 两条长边垂直，所有短边水平；
# 短边之间的间距按左边长边各段的原始 UV 长度（拉直保长）分配

bl_info = {
    "name": "发丝UV长条拉直规整",
    "author": "Custom",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "category": "Mesh",
}
import bpy
import bmesh
import mathutils


def hungarian(cost_matrix):
    """匈牙利算法：给定 n×n 代价矩阵，返回最小代价完美匹配。
    cost_matrix[i][j] = 将行 i 分配给列 j 的代价。
    返回: assignment[i] = 分配给行 i 的列索引
    O(n³)，输入不修改。
    """
    n = len(cost_matrix)
    u = [0] * (n + 1)    # 行势
    v = [0] * (n + 1)    # 列势
    p = [0] * (n + 1)    # p[j] = 分配给列 j 的行 (1-indexed)
    way = [0] * (n + 1)  # 增广路径回溯

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float('inf')] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float('inf')
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [0] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    return assignment


class UV_OT_HairStripNormalize(bpy.types.Operator):
    bl_idname = "uv.hair_strip_normalize"
    bl_label = "一键发丝UV长条拉直规整"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "请选中网格模型，进入编辑模式")
            return {'CANCELLED'}
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        sel_edges = [e for e in bm.edges if e.select]

        components = []
        used = set()
        # 调试打印所有选中边
        print("=====所有选中边总数：", len(sel_edges))
        for test_e in sel_edges:
            vert_coords = [tuple(round(v.co[i],4) for i in range(3)) for v in test_e.verts]
            print("选中边顶点坐标：", vert_coords)

        for start in sel_edges:
            if start in used:
                continue
            comp = []
            stack = [start]
            used.add(start)
            while stack:
                e = stack.pop()
                comp.append(e)
                for v in e.verts:
                    for nb in v.link_edges:
                        if nb.select and nb not in used:
                            used.add(nb)
                            stack.append(nb)
            components.append(comp)

        print("=====最终连通分组数量：", len(components))
        for idx, comp in enumerate(components):
            print(f"分组{idx} 包含边数：{len(comp)}")

        if len(sel_edges) < 2:
            self.report({'ERROR'}, "至少选中左右两条长边")
            return {'CANCELLED'}

        # 把选中边按共享顶点分成连通分量，期望恰好两条独立边线
        components = []
        used = set()
        for start in sel_edges:
            if start in used:
                continue
            comp = []
            stack = [start]
            used.add(start)
            while stack:
                e = stack.pop()
                comp.append(e)
                for v in e.verts:
                    for nb in v.link_edges:
                        if nb.select and nb not in used:
                            used.add(nb)
                            stack.append(nb)
            components.append(comp)

        if len(components) != 2:
            self.report({'ERROR'}, f"选中的边必须构成左右两条独立边线（当前 {len(components)} 条），请只选中两条长边")
            return {'CANCELLED'}

        # 边线内按拓扑从一端走到另一端，得到有序顶点（不依赖 UV 坐标，弯曲也正确）
        def order_chain(edges):
            edge_set = set(edges)
            deg = {}
            for e in edges:
                for v in e.verts:
                    deg[v] = deg.get(v, 0) + 1
            endpoints = [v for v, d in deg.items() if d == 1]
            if len(endpoints) != 2:
                return None
            order = [endpoints[0]]
            cur = endpoints[0]
            prev = None
            while cur != endpoints[1]:
                nxt = None
                for e in cur.link_edges:
                    if e in edge_set and e != prev:
                        nxt = e
                        break
                if nxt is None:
                    return None
                cur = nxt.other_vert(cur)
                order.append(cur)
                prev = nxt
            return order

        chain_a = order_chain(components[0])
        chain_b = order_chain(components[1])
        if chain_a is None or chain_b is None:
            self.report({'ERROR'}, "边线必须是两端开放的连续路径")
            return {'CANCELLED'}
        if len(chain_a) != len(chain_b):
            self.report({'ERROR'}, "左右两条边线顶点数量不一致，无法一一对应")
            return {'CANCELLED'}

        # 调试：打印两条链的顶点坐标
        print("=====chain_a (components[0]) 有序顶点=====")
        for i, v in enumerate(chain_a):
            print(f"  chain_a[{i}]: index={v.index}, co=({v.co.x:.4f},{v.co.y:.4f},{v.co.z:.4f})")
        print("=====chain_b (components[1]) 有序顶点=====")
        for i, v in enumerate(chain_b):
            print(f"  chain_b[{i}]: index={v.index}, co=({v.co.x:.4f},{v.co.y:.4f},{v.co.z:.4f})")

        # 调试：打印每条选中边的顶点归属信息
        print("=====所有选中边详细信息=====")
        a_set = set(chain_a)
        b_set = set(chain_b)
        for idx, comp in enumerate(components):
            print(f"--- 分组{idx} 的边 ---")
            for e in comp:
                v0, v1 = e.verts
                in_a0 = v0 in a_set
                in_a1 = v1 in a_set
                in_b0 = v0 in b_set
                in_b1 = v1 in b_set
                print(f"  边 v{v0.index}({'A' if in_a0 else 'B' if in_b0 else '?'})-v{v1.index}({'A' if in_a1 else 'B' if in_b1 else '?'}) "
                      f"coords: ({v0.co.x:.4f},{v0.co.y:.4f},{v0.co.z:.4f}) - ({v1.co.x:.4f},{v1.co.y:.4f},{v1.co.z:.4f})")

        # 用匈牙利算法建立左右顶点一一对应
        # 代价矩阵：有横档边 → cost = |i-j|（索引接近优先）；无边 → cost = n²（严厉惩罚，尽量不用）
        b_index = {v: i for i, v in enumerate(chain_b)}  # vertex -> index in chain_b
        n = len(chain_a)

        # 先收集每个 chain_a 顶点的边邻接候选，同时检查是否有孤立顶点
        edge_candidates = []  # edge_candidates[i] = set of chain_b vertices connected to chain_a[i]
        for i, v in enumerate(chain_a):
            cand = set()
            for e in v.link_edges:
                other = e.other_vert(v)
                if other in b_set:
                    cand.add(other)
            edge_candidates.append(cand)
            if not cand:
                print(f"=====错误：chain_a[{i}] v{v.index} 没有连接到chain_b的边！=====")
                self.report({'ERROR'}, "左右边线之间缺少连接边（横档），无法建立对应")
                return {'CANCELLED'}

        # 构建 n×n 代价矩阵
        cost = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if chain_b[j] in edge_candidates[i]:
                    cost[i][j] = abs(i - j)      # 有边：索引越接近代价越小
                else:
                    cost[i][j] = n * n            # 无边：高代价，仅在必要时使用

        assignment = hungarian(cost)  # assignment[i] = chain_b 中分配给 chain_a[i] 的列索引
        partner = {chain_a[i]: chain_b[assignment[i]] for i in range(n)}

        # 调试打印匹配结果
        for i in range(n):
            candidates = edge_candidates[i]
            j = assignment[i]
            bj = chain_b[j]
            edge_type = "有边" if bj in candidates else "无边(惩罚匹配)"
            if len(candidates) > 1:
                cand_str = ", ".join(f"chain_b[{b_index[bv]}]" for bv in candidates)
                print(f"匈牙利：chain_a[{i}] v{chain_a[i].index} 候选=[{cand_str}] → chain_b[{j}] v{bj.index} ({edge_type}, 代价={cost[i][j]})")
            elif len(candidates) == 1:
                bv = list(candidates)[0]
                print(f"匈牙利：chain_a[{i}] v{chain_a[i].index} 单候选 chain_b[{b_index[bv]}] → chain_b[{j}] v{bj.index} ({edge_type}, 代价={cost[i][j]})")

        left_order = chain_a
        right_order = [partner[v] for v in chain_a]

        # 取顶点在选中边上的 UV
        # 不依赖 loop.edge（受面 winding 影响），而是通过选中边的 link_faces 找面，再从面里定位顶点
        def vert_uv(v):
            for e in v.link_edges:
                if e.select:
                    for face in e.link_faces:
                        for loop in face.loops:
                            if loop.vert == v:
                                return loop[uv_layer].uv.copy()
            # 调试：打印失败的顶点
            print(f"=====vert_uv 失败：v{v.index} co=({v.co.x:.4f},{v.co.y:.4f},{v.co.z:.4f})=====")
            print(f"  link_edges ({len(v.link_edges)}条):")
            for e in v.link_edges:
                v0, v1 = e.verts
                print(f"    v{v0.index}-v{v1.index} select={e.select}")
            print(f"  link_faces ({len(v.link_faces)}个):")
            for f in v.link_faces:
                f_verts = [fv.index for fv in f.verts]
                print(f"    face verts={f_verts}")
                for lp in f.loops:
                    if lp.vert == v:
                        print(f"      loop.vert==v found, loop.edge=v{lp.edge.verts[0].index}-v{lp.edge.verts[1].index} select={lp.edge.select}, uv=({lp[uv_layer].uv.x:.4f},{lp[uv_layer].uv.y:.4f})")
            return None

        print("=====开始收集 UV =====")
        left_uv = [vert_uv(v) for v in left_order]
        right_uv = [vert_uv(v) for v in right_order]
        failed = [(side, i, v.index) for side, uv_list, order in
                   [('left', left_uv, left_order), ('right', right_uv, right_order)]
                   for i, (u, v) in enumerate(zip(uv_list, order)) if u is None]
        if failed:
            print(f"=====UV 收集失败顶点 ({len(failed)}个)=====")
            for side, i, vi in failed:
                print(f"  {side}[{i}] v{vi}")
            self.report({'ERROR'}, "部分顶点在选中边上没有 UV，请确认选中边线完整")
            return {'CANCELLED'}

        # 间距 = 左边线各段原始 UV 长度（拉直保长），逐段累加 Y；
        # 左右 X 固定为各自首顶点原始 X，Y 同步实现短边水平
        left_x = left_uv[0].x
        right_x = right_uv[0].x
        y = left_uv[0].y
        new_uv = {}
        for i in range(len(left_order)):
            if i > 0:
                y += (left_uv[i] - left_uv[i - 1]).length
            new_uv[left_order[i]] = mathutils.Vector((left_x, y))
            new_uv[right_order[i]] = mathutils.Vector((right_x, y))

        for v, uv in new_uv.items():
            for loop in v.link_loops:
                loop[uv_layer].uv = uv

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"UV 长条已规整为矩形竖条（{len(left_order) - 1} 段）完成")
        return {'FINISHED'}

# 挂载到 ModTool 公共面板
def draw_panel_button(self, context):
    layout = self.layout
    layout.operator(UV_OT_HairStripNormalize.bl_idname)

classes = [UV_OT_HairStripNormalize]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_PT_ModToolBasePanel.append(draw_panel_button)

def unregister():
    bpy.types.VIEW3D_PT_ModToolBasePanel.remove(draw_panel_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
    print("执行方式：UV编辑器顶部菜单/搜索命令：一键发丝UV长条拉直规整")
