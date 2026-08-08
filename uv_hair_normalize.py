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

        # 用连接两条边线的横档边建立左右顶点对应
        # 先收集所有 chain_a 顶点到 chain_b 顶点的连接（可能有三角化导致的多对多）
        # 再用索引匹配消除歧义：chain_a[i] 对应 chain_b 中索引最接近 i 的那个
        b_index = {v: i for i, v in enumerate(chain_b)}  # vertex -> index in chain_b
        partner = {}
        for i, v in enumerate(chain_a):
            candidates = set()
            for e in v.link_edges:
                other = e.other_vert(v)
                if other in b_set:
                    candidates.add(other)
            if not candidates:
                print(f"=====错误：chain_a[{i}] v{v.index} 没有连接到chain_b的边！=====")
                self.report({'ERROR'}, "左右边线之间缺少连接边（横档），无法建立对应")
                return {'CANCELLED'}
            # 选 chain_b 中索引最接近 i 的那个（三角化对角线会连到 i±1）
            best = min(candidates, key=lambda bv: abs(b_index[bv] - i))
            partner[v] = best
            if len(candidates) > 1:
                print(f"注意：chain_a[{i}] v{v.index} 连接多个chain_b顶点: "
                      f"{[(bv.index, b_index[bv]) for bv in candidates]}，选择 chain_b[{b_index[best]}] v{best.index}")

        left_order = chain_a
        right_order = [partner[v] for v in chain_a]
        if len(set(right_order)) != len(right_order):
            self.report({'ERROR'}, "左右顶点对应关系重复，无法建立一一对应")
            return {'CANCELLED'}

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

# 挂载到 UV 编辑器顶部菜单
def draw_button(self, context):
    self.layout.operator(UV_OT_HairStripNormalize.bl_idname)

classes = [UV_OT_HairStripNormalize]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.IMAGE_MT_uvs.append(draw_button)

def unregister():
    bpy.types.IMAGE_MT_uvs.remove(draw_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
    print("执行方式：UV编辑器顶部菜单/搜索命令：一键发丝UV长条拉直规整")
