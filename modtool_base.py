bl_info = {
    "name": "ERModTool 基础面板",
    "author": "Custom",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "category": "Mesh",
}
import bpy

# 公共面板，所有工具共用
class VIEW3D_PT_ModToolBasePanel(bpy.types.Panel):
    bl_label = "Eldenring模型工具"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ERModTool"

    def draw(self, context):
        layout = self.layout
        # 其他插件会自动在这里追加按钮

classes = [VIEW3D_PT_ModToolBasePanel]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()