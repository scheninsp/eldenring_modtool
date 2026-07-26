# 使用方式：选中 Mesh 然后执行
# 目标：将选中的 Mesh 下所有不同材质的 SubMesh 拆解为 Mesh
# 修复：自动复制骨架修改器、预处理变换、修复FBX蒙皮错乱
bl_info = {
    "name": "按材质拆分Mesh工具",
    "author": "Custom",
    "version": (1, 2),
    "blender": (3, 6, 0),
    "category": "Mesh",
}
import bpy

def remove_empty_vertex_groups(obj):
    """清理物体内部没有任何有效权重的空顶点组"""
    if obj.type != "MESH" or not obj.vertex_groups:
        return
    obj.update_from_editmode()
    used_indices = set()
    for v in obj.data.vertices:
        for g in v.groups:
            if g.weight > 0.0:
                used_indices.add(g.group)
    # 反向遍历防止索引移位
    for idx in reversed(range(len(obj.vertex_groups))):
        if idx not in used_indices:
            obj.vertex_groups.remove(obj.vertex_groups[idx])

def copy_armature_modifier(src_obj, target_obj):
    """更新目标物体的骨架修改器：Blender 分离时会复制 modifier 但 object 引用可能为空"""
    src_arm_mods = [m for m in src_obj.modifiers if m.type == 'ARMATURE']
    if not src_arm_mods:
        return
    tgt_arm_mods = [m for m in target_obj.modifiers if m.type == 'ARMATURE']
    for i, src_mod in enumerate(src_arm_mods):
        if i < len(tgt_arm_mods):
            mod = tgt_arm_mods[i]          # 更新已有的，避免重复
        else:
            mod = target_obj.modifiers.new(name=src_mod.name, type='ARMATURE')
        mod.object = src_mod.object
        mod.use_bone_envelopes = src_mod.use_bone_envelopes
        mod.use_vertex_groups = src_mod.use_vertex_groups

class MESH_OT_SeparateByMaterial(bpy.types.Operator):
    bl_idname = "mesh.separate_by_material_clean_vgroup"
    bl_label = "按材质拆分Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        sel_objs = [o for o in context.selected_objects if o.type == "MESH"]
        if not sel_objs:
            self.report({'ERROR'}, "请先选中至少一个网格物体！")
            return {'CANCELLED'}
        success = 0
        for src_obj in sel_objs:
            base_name = src_obj.name
            # 预处理：应用变换，避免分离后坐标错乱
            bpy.context.view_layer.objects.active = src_obj
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            
            before_set = set(context.view_layer.objects)
            # 选中激活目标物体
            bpy.ops.object.select_all(action='DESELECT')
            src_obj.select_set(True)
            context.view_layer.objects.active = src_obj
            # 进入编辑模式拆分
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.separate(type='MATERIAL')
            bpy.ops.object.mode_set(mode='OBJECT')
            # 找出本次拆分新生成物体
            after_set = set(context.view_layer.objects)
            new_objs = list(after_set - before_set)
            
            # 原物体重命名+清理顶点组
            src_obj.name = f"{base_name}_001"
            remove_empty_vertex_groups(src_obj)

            # 新物体依次命名 + 复制骨架修改器 + 清理顶点组
            index = 2
            for o in new_objs:
                o.name = f"{base_name}_{index:03d}"
                # 关键修复：复制骨架绑定修改器
                copy_armature_modifier(src_obj, o)
                remove_empty_vertex_groups(o)
                index += 1
            success += 1

            # 统一所有拆分物体绑定同一骨架父级（FBX 导出需要父子关系）
            arm_obj = None
            for mod in src_obj.modifiers:
                if mod.type == "ARMATURE" and mod.object:
                    arm_obj = mod.object
                    break
            if arm_obj:
                all_parts = [src_obj] + new_objs
                bpy.ops.object.select_all(action='DESELECT')
                for part in all_parts:
                    part.select_set(True)
                arm_obj.select_set(True)
                context.view_layer.objects.active = arm_obj
                bpy.ops.object.parent_set(type='ARMATURE', keep_transform=True)

        self.report({'INFO'}, f"完成{success}个模型拆分，已自动复制骨架绑定、清理空顶点组")
        return {'FINISHED'}
# 面板绘制按钮
def draw_tool_button(self, context):
    layout = self.layout
    layout.operator(MESH_OT_SeparateByMaterial.bl_idname)
classes = [MESH_OT_SeparateByMaterial]
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_PT_ModToolBasePanel.append(draw_tool_button)
def unregister():
    bpy.types.VIEW3D_PT_ModToolBasePanel.remove(draw_tool_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
if __name__ == "__main__":
    register()
    print("拆分工具已加载：按材质拆分Mesh(自动修复骨架绑定)")