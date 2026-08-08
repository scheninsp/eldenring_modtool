bl_info = {
    "name": "EldenRing ModTool",
    "author": "Custom",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "category": "Mesh",
}
import sys
# ===== 重载缓存清理核心代码（必须放最前面）=====
if "uv_hair_normalize" in locals():
    # 插件被重载时，删除本包所有子模块缓存
    package_prefix = __name__ + "."
    # 遍历所有缓存模块，删除本插件包内所有py
    for mod_name in tuple(sys.modules.keys()):
        if mod_name == __name__ or mod_name.startswith(package_prefix):
            del sys.modules[mod_name]
# ==============================================
# 再导入子模块
from . import modtool_base
from . import clean_vertexgroup
from . import separate_mesh
from . import uv_hair_normalize

def register():
    modtool_base.register()
    clean_vertexgroup.register()
    separate_mesh.register()
    uv_hair_normalize.register()

def unregister():
    uv_hair_normalize.unregister()
    separate_mesh.unregister()
    clean_vertexgroup.unregister()
    modtool_base.unregister()

if __name__ == "__main__":
    register()