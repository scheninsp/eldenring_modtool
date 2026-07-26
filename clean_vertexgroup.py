# 使用方式：选中 Mesh 然后执行
# 目标：删除选中 Mesh 下的所有无权重空顶点组

bl_info = {
    "name": "清理空顶点组工具",
    "author": "Custom",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "category": "Mesh",
}
import bpy

class MESH_OT_CleanEmptyVertexGroups(bpy.types.Operator):
    bl_idname = "mesh.clean_empty_vgroups"
    bl_label = "删除无权重空顶点组"

    def execute(self, context):
        def remove_empty_vertex_groups(obj):
            if obj.type != 'MESH':
                return 0
            mesh = obj.data
            vgroups_to_remove = []
            for vg in obj.vertex_groups:
                has_weight = False
                for v in mesh.vertices:
                    try:
                        if vg.weight(v.index) > 0.00001:
                            has_weight = True
                            break
                    except RuntimeError:
                        continue
                if not has_weight:
                    vgroups_to_remove.append(vg.name)
            for vg_name in reversed(vgroups_to_remove):
                vg = obj.vertex_groups.get(vg_name)
                if vg:
                    obj.vertex_groups.remove(vg)
            return len(vgroups_to_remove)

        total_del = 0
        for obj in context.selected_objects:
            cnt = remove_empty_vertex_groups(obj)
            total_del += cnt
            if cnt > 0:
                self.report({'INFO'}, f"{obj.name} 移除{cnt}个空顶点组")
        if total_del == 0:
            self.report({'INFO'}, "选中物体无空顶点组")
        return {'FINISHED'}

# 挂载到 ModTool 面板
def draw_button(self, context):
    layout = self.layout
    layout.operator("mesh.clean_empty_vgroups")

classes = [MESH_OT_CleanEmptyVertexGroups]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # 挂载绘制函数到公共面板
    bpy.types.VIEW3D_PT_ModToolBasePanel.append(draw_button)

def unregister():
    # 移除绘制函数
    bpy.types.VIEW3D_PT_ModToolBasePanel.remove(draw_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()