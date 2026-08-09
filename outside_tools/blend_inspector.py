"""Parse .blend file: version, data types, external addon dependencies"""
import gzip, struct, collections, os, sys, time

def inspect(path):
    t0 = time.time()

    # --- Read file ---
    with open(path, 'rb') as f:
        head = f.read(12)
    is_gzip = (head[:2] == b'\x1f\x8b')
    if is_gzip:
        with gzip.open(path, 'rb') as f:
            raw = f.read()
    else:
        with open(path, 'rb') as f:
            raw = f.read()

    fsize = os.path.getsize(path)
    print(f'File: {os.path.basename(path)}')
    print(f'Size: {fsize:,} bytes ({fsize/1024/1024:.1f} MB)')
    if is_gzip:
        print(f'Format: gzip compressed (uncompressed {len(raw)/1024/1024:.1f} MB)')

    # --- Parse file header ---
    magic = raw[:7].decode('ascii')
    ptr_char = chr(raw[7])
    endian_char = chr(raw[8])
    ver_str = raw[9:12].decode('ascii')
    is_64bit = (ptr_char == '-')

    print(f'Version: Blender {ver_str[0]}.{ver_str[1]}.{ver_str[2:]}'
          f' ({("64" if is_64bit else "32")}-bit,'
          f' {"LE" if endian_char == "v" else "BE"})')
    print(f'Load time: {time.time()-t0:.1f}s')

    # --- Scan all blocks ---
    old_addr_sz = 8 if is_64bit else 4
    header_sz = 4 + 4 + old_addr_sz + 4 + 4  # 24 (64-bit) or 20 (32-bit)

    pos = 12
    block_list = []  # (code, header_pos, data_size, sdna_idx, count)
    while pos + header_sz <= len(raw):
        code_bytes = raw[pos:pos+4]
        code = code_bytes.rstrip(b'\x00').decode('ascii', errors='replace')
        size = struct.unpack_from('<I', raw, pos + 4)[0]
        if is_64bit:
            sdna_idx = struct.unpack_from('<I', raw, pos + 16)[0]
            count = struct.unpack_from('<I', raw, pos + 20)[0]
        else:
            sdna_idx = struct.unpack_from('<I', raw, pos + 12)[0]
            count = struct.unpack_from('<I', raw, pos + 16)[0]
        block_list.append((code, pos, size, sdna_idx, count))
        pos += header_sz + size

    code_counts = collections.Counter(b[0] for b in block_list)
    print(f'\n=== Blocks ({len(block_list)}) [{time.time()-t0:.1f}s] ===')
    for t, c in code_counts.most_common():
        print(f'  {t:10s} {c:>8,}')

    # --- Find DNA1 block ---
    dna_block = None
    for b in block_list:
        if b[0] == 'DNA1':
            dna_block = b
            break
    if dna_block is None:
        print('Error: DNA1 block not found')
        return

    # --- Parse SDNA (DNA1 block data) ---
    # Format: "SDNA" "NAME" nr_names names... "TYPE" nr_types types... "TLEN" lengths... "STRC" struct_entries
    dna_start = dna_block[1] + header_sz
    dna_data = raw[dna_start:dna_start + dna_block[2]]
    dna_size = len(dna_data)
    print(f'  DNA1 block: data_size={dna_block[2]:,}')

    def read_tagged_strings(data, off, expected_tag):
        """Read: tag(4B) + count(4B) + null-term strings. Returns (count, list, new_off)."""
        tag = data[off:off+4].decode('ascii', errors='replace')
        if tag != expected_tag:
            print(f'  NOTE: expected tag "{expected_tag}", got "{tag}" at off={off}')
        off += 4
        count = struct.unpack_from('<I', data, off)[0]; off += 4
        entries = []
        for _ in range(count):
            end = data.find(b'\x00', off)
            if end == -1:
                break
            entries.append(data[off:end].decode('ascii', errors='replace'))
            off = end + 1
        off = (off + 3) & ~3
        return count, entries, off

    off = 4  # skip "SDNA" identifier

    nr_names, names, off = read_tagged_strings(dna_data, off, 'NAME')
    print(f'  NAME: {nr_names} names')

    nr_types, type_names, off = read_tagged_strings(dna_data, off, 'TYPE')
    print(f'  TYPE: {nr_types} types, off now at {off} of {dna_size} (left={dna_size-off})')
    # Show next bytes after types
    if off + 12 <= dna_size:
        nxt = dna_data[off:off+12].hex()
        nxt_asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in dna_data[off:off+12])
        print(f'  Next bytes: {nxt}  [{nxt_asc}]')

    # TLEN: tag(4B) + shorts(nr_types * 2B) (NO count field — uses nr_types)
    tlen_tag = dna_data[off:off+4].decode('ascii', errors='replace')
    if tlen_tag != 'TLEN':
        print(f'  NOTE: expected "TLEN", got "{tlen_tag}"')
    off += 4
    nr_lengths = nr_types
    type_lengths = []
    for _ in range(nr_lengths):
        if off + 2 > dna_size:
            break
        type_lengths.append(struct.unpack_from('<H', dna_data, off)[0])
        off += 2
    print(f'  TLEN: {len(type_lengths)} lengths')

    # STRC: tag(4B) + entries(nr_structs * 4B) (NO count field?)
    # Let's see what follows TLEN
    if off + 8 <= dna_size:
        nxt = dna_data[off:off+8].hex()
        nxt_asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in dna_data[off:off+8])
        print(f'  After TLEN: {nxt}  [{nxt_asc}]')

    strc_tag = dna_data[off:off+4].decode('ascii', errors='replace')
    if strc_tag != 'STRC':
        print(f'  NOTE: expected "STRC", got "{strc_tag}"')
    off += 4
    # After STRC tag, there may or may not be a count field. We read until we've consumed all.
    # The struct entries are (type_idx:2B, name_idx:2B) pairs.
    # nr_structs = total number of such pairs across all types.
    # We'll just read until we can't anymore or hit another tag.
    nr_structs = struct.unpack_from('<I', dna_data, off)[0]; off += 4
    print(f'  STRC: nr_structs field = {nr_structs}')

    type_field_entries = [[] for _ in range(len(type_names))]
    fields_parsed = 0
    while fields_parsed < nr_structs and off + 4 <= dna_size:
        ft_idx = struct.unpack_from('<H', dna_data, off)[0]; off += 2
        fn_idx = struct.unpack_from('<H', dna_data, off)[0]; off += 2
        fn = names[fn_idx] if fn_idx < len(names) else '?%d' % fn_idx
        ft = type_names[ft_idx] if ft_idx < len(type_names) else '?%d' % ft_idx
        if ft_idx < len(type_field_entries):
            type_field_entries[ft_idx].append((ft, fn))
        fields_parsed += 1

    type_fields = {}
    for ti in range(len(type_names)):
        if type_field_entries[ti]:
            type_fields[type_names[ti]] = type_field_entries[ti]

    print(f'  STRC: {nr_structs} struct entries ({fields_parsed} parsed)')

    # --- Count actual DATA block type usage ---
    data_t0 = time.time()
    data_usage = collections.Counter()
    for code, hdr_pos, data_size, sdna_idx, count in block_list:
        if code == 'DATA' and 0 <= sdna_idx < len(type_names):
            data_usage[type_names[sdna_idx]] += count

    print(f'\n=== DATA type usage ({sum(data_usage.values()):,} instances) [{time.time()-data_t0:.1f}s] ===')
    for t, c in data_usage.most_common(60):
        print(f'  {t:50s} {c:>8,}')
    remaining = len(data_usage) - 60
    if remaining > 0:
        print(f'  ... and {remaining} more types')

    # --- Detect non-native types (possible addon data) ---
    # Blender 2.83 native types
    native = {
        'Action', 'Actuator', 'AnimData', 'Area', 'Armature', 'ArmatureModifier',
        'ArrayModifier', 'bAction', 'bActionGroup', 'bArmature', 'bConstraint',
        'BevelModifier', 'BezierTriple', 'bGPdata', 'bGPDframe', 'bGPDlayer',
        'bGPDpalette', 'bGPDpalettecolor', 'bGPDstroke', 'bNode', 'bNodeSocket',
        'bNodeTree', 'Bone', 'BooleanModifier', 'Brush', 'BuildModifier',
        'CacheFile', 'Camera', 'CastModifier', 'Cloth', 'ClothCollision',
        'ClothSimSettings', 'Collection', 'CollisionModifier',
        'ColorManagedDisplaySettings', 'ColorManagedViewSettings',
        'ColorMapping', 'Constraint', 'Controller', 'CorrectiveSmoothModifier',
        'Curve', 'CurveMapping', 'CurveMapPoint', 'CustomData', 'CustomDataLayer',
        'DataTransferModifier', 'DecimateModifier', 'DisplaceModifier',
        'DriverTarget', 'DriverVar', 'DynamicPaintModifier', 'EdgeSplitModifier',
        'EditLatt', 'Effect', 'ExplodeModifier', 'FCurve', 'Field',
        'FileSelectParams', 'FluidDomainSettings', 'FluidEffectorSettings',
        'FluidFlowSettings', 'FluidModifier', 'FluidSimSettings',
        'FreestyleLineSet', 'FreestyleLineStyle', 'FreestyleModuleSettings',
        'FreestyleSettings', 'GPencil', 'GPencilModifier', 'GPencilSculptSettings',
        'Group', 'HookModifier', 'ID', 'IDProperty', 'Image', 'ImageFormatData',
        'ImageUser', 'Key', 'KeyBlock', 'KeyMap', 'KeyMapItem', 'KeyingSet',
        'KeyingSetInfo', 'KeyingSetPath', 'Lamp', 'LaplacianDeformModifier',
        'LaplacianSmoothModifier', 'Lattice', 'LatticeModifier', 'LayerCollection',
        'Library', 'Light', 'LineStyleGeometryModifier', 'LineStyleModifier',
        'ListBase', 'Mask', 'MaskLayer', 'MaskModifier', 'MaskParent',
        'MaskSpline', 'MaskSplinePoint', 'MaskSplinePointUW', 'Material',
        'Mesh', 'MeshDeformModifier', 'MeshModifier', 'MetaBall',
        'MirrorModifier', 'ModifierData', 'MovieCache', 'MovieClip',
        'MovieTracking', 'MovieTrackingCamera', 'MovieTrackingDopesheet',
        'MovieTrackingMarker', 'MovieTrackingObject', 'MovieTrackingPlaneTrack',
        'MovieTrackingPlaneMarker', 'MovieTrackingReconstruction',
        'MovieTrackingSettings', 'MovieTrackingStabilization',
        'MovieTrackingTrack', 'MultiresModifier', 'Multires', 'NlaStrip',
        'NlaTrack', 'Node', 'NodeGroup', 'NodeInstanceHash', 'NodesModifier',
        'NodeSocket', 'Object', 'OceanModifier', 'OceanTexData', 'PackedFile',
        'Paint', 'PaintCurve', 'Palette', 'Particle', 'ParticleBrush',
        'ParticleData', 'ParticleDupliWeight', 'ParticleEditSettings',
        'ParticleKey', 'ParticleModifier', 'ParticleSettings', 'ParticleSystem',
        'PointCache', 'PointCloud', 'PreviewImage', 'Property', 'RegionView3D',
        'RenderData', 'RenderEngine', 'RenderLayer', 'RenderPass', 'RenderProfile',
        'RigidBodyJoint', 'RigidBodyOb', 'RigidBodyWorld', 'ScrArea', 'Screen',
        'Sensor', 'Sequence', 'SessionUUID', 'ShaderFx', 'ShapeKey',
        'ShrinkwrapModifier', 'SimpleDeformModifier', 'Simulation',
        'SkinModifier', 'SmokeModifier', 'SoftBody', 'SolidifyModifier', 'Sound',
        'SpaceAction', 'SpaceButs', 'SpaceClip', 'SpaceConsole', 'SpaceFile',
        'SpaceGraph', 'SpaceImage', 'SpaceInfo', 'SpaceNla', 'SpaceNode',
        'SpaceOutliner', 'SpaceProperties', 'SpaceSeq', 'SpaceStatusBar',
        'SpaceText', 'SpaceTopBar', 'SpaceUserPref', 'SpaceView3D', 'Speaker',
        'SubsurfModifier', 'SurfaceDeformModifier', 'SurfaceModifier', 'Tex',
        'Text', 'TextBox', 'TextLine', 'Texture', 'ThemeSpace', 'ThemeUI',
        'ToolSettings', 'TriangulateModifier', 'UILayout', 'UvSculpt', 'VFont',
        'View3D', 'ViewLayer', 'Volume', 'WarpModifier', 'WaveModifier',
        'WeightedNormalModifier', 'Window', 'WireframeModifier', 'wmGesture',
        'wmKeyConfig', 'wmKeyMap', 'wmKeyMapItem', 'wmOperator', 'wmOperatorType',
        'wmWindow', 'wmWindowManager', 'WorkSpace', 'World', 'bTheme', 'MotionPath',
        'bPose', 'PoseChannel', 'Depsgraph', 'DepsObject', 'FieldSettings',
        'PartDeflect', 'SmokeDomainSettings', 'SmokeFlowSettings',
        'SmokeCollSettings', 'DynamicPaintSurface', 'DynamicPaintCanvasSettings',
        'DynamicPaintBrushSettings', 'StudioLight', 'WorkSpaceDataTemplate',
        'AviCodecData', 'QuicktimeCodecData', 'FFMpegCodecData',
        'PointLight', 'SpotLight', 'SunLight', 'AreaLight',
        'GPencilLayer', 'GPencilFrame', 'GPencilStroke', 'GPencilPoint',
        'MVert', 'MEdge', 'MFace', 'MLoop', 'MPoly', 'MLoopUV', 'MLoopCol',
        'MDeformVert', 'MDeformWeight', 'MTFace', 'MTexPoly',
        'MCol', 'MeshDeformBind', 'MeshDeformVertex',
        'bDeformGroup', 'PartEff', 'PartImP', 'PartInfo', 'PartKey',
    }

    non_native = sorted(t for t in data_usage if t not in native)
    print(f'\n=== Non-native types (possible addon data) [{len(non_native)} types] ===')
    if non_native:
        for t in non_native:
            print(f'  {t:50s} {data_usage[t]:>8,} instances')
            if t in type_fields:
                fstr = ', '.join('%s %s' % (ft, fn) for ft, fn in type_fields[t][:10])
                if len(type_fields[t]) > 10:
                    fstr += ', ... (+%d more)' % (len(type_fields[t]) - 10)
                print(f'    Fields: [{fstr}]')
    else:
        print('  (none)')

    # --- Summary ---
    sep = '=' * 70
    print(f'\n{sep}')
    print('Summary')
    print(sep)
    print(f'  File:              {os.path.basename(path)}')
    print(f'  Blender version:   {ver_str[0]}.{ver_str[1]}.{ver_str[2:]} ({("64" if is_64bit else "32")}-bit)')
    print(f'  Gzip compressed:   {"yes" if is_gzip else "no"}')
    print(f'  File size:         {fsize/1024/1024:.1f} MB')
    print(f'  Data types:        {len(data_usage)}')
    print(f'  Total instances:   {sum(data_usage.values()):,}')
    print(f'  Total blocks:      {len(block_list)}')
    if non_native:
        print(f'  Possible addons:   {len(non_native)} type(s)')
        for t in non_native:
            print(f'    - "{t}" ({data_usage[t]} instances)')
    print(f'  Total time:        {time.time()-t0:.1f}s')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python blend_inspector.py <file.blend>')
        sys.exit(1)
    inspect(sys.argv[1])
