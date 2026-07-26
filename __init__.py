bl_info = {
    "name": "EldenRing ModTool",
    "author": "Custom",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "category": "Mesh",
}

# 导入所有模块
from . import modtool_base
from . import clean_vertexgroup
from . import separate_mesh

def register():
    modtool_base.register()
    clean_vertexgroup.register()
    separate_mesh.register()

def unregister():
    separate_mesh.unregister()
    clean_vertexgroup.unregister()
    modtool_base.unregister()

if __name__ == "__main__":
    register()