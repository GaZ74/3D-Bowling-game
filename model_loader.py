import numpy as np
import trimesh
from OpenGL.GL import *
from PIL import Image

RGB_GRAFFITI_NODES = {"Line002_podsvetka_0", "Line003_podsvetka_0"}
WARM_CEILING_LIGHT_PREFIX = "Cylinder003_Material #191_"
# The right-wall neon mesh sits nearly coplanar with the imported wall surface.
# Nudge it slightly into the alley to prevent depth-fighting/partial occlusion.
NODE_SOURCE_OFFSETS = {"Line002_podsvetka_0": (0.0, 0.0, -0.05)}


class Model:
    def __init__(self, path, target_size, anchor="center", use_materials=False,
                 exclude_name_tokens=()):
        scene = trimesh.load_scene(path)
        meshes = []
        source_meshes = []
        for node_name in scene.graph.nodes_geometry:
            transform, geometry_name = scene.graph[node_name]
            mesh = scene.geometry[geometry_name].copy()
            mesh.apply_transform(transform)
            if isinstance(mesh, trimesh.Trimesh):
                source_offset = NODE_SOURCE_OFFSETS.get(node_name)
                if source_offset is not None:
                    mesh.apply_translation(source_offset)
                source_meshes.append(mesh)
                excluded = any(
                    token.casefold() in f"{node_name} {geometry_name}".casefold()
                    for token in exclude_name_tokens
                )
                if not excluded:
                    meshes.append((node_name, mesh))

        if not meshes:
            raise ValueError(f"No mesh geometry found in {path}")

        # Keep the room's original coordinate frame even when replaceable
        # static props (such as its pins) are omitted from drawing.
        all_vertices = np.concatenate([mesh.vertices for mesh in source_meshes])
        low = all_vertices.min(axis=0)
        high = all_vertices.max(axis=0)
        center = (low + high) / 2

        # For a pin, put its base at y=0. The project uses Y as vertical.
        if anchor == "bottom":
            center[1] = low[1]

        largest_dimension = max((high - low).max(), 1e-6)
        scale = target_size / largest_dimension
        self.extents = (high - low) * scale
        self.source_center = center.copy()
        self.normalization_scale = scale
        self.use_materials = use_materials

        self.parts = []
        self.material_groups = []
        group_lookup = {}
        for node_name, mesh in meshes:
            vertices = (mesh.vertices - center) * scale
            faces = mesh.faces
            normals = mesh.face_normals
            if not use_materials:
                self.parts.append((vertices, faces, normals))
                continue

            visual = mesh.visual
            material = getattr(visual, "material", None)
            factor = getattr(material, "baseColorFactor", None)
            if factor is None:
                color = (1.0, 1.0, 1.0)
            else:
                factor = np.asarray(factor, dtype=float)
                if factor.max(initial=0.0) > 1.0:
                    factor /= 255.0
                color = tuple(np.clip(factor[:3], 0.0, 1.0))

            texture = getattr(material, "baseColorTexture", None)
            texture_key = None
            if texture is not None:
                texture_key = (texture.size, hash(texture.tobytes()))
            if node_name in RGB_GRAFFITI_NODES:
                dynamic_color_tag = "rgb_graffiti"
            elif node_name.startswith(WARM_CEILING_LIGHT_PREFIX):
                dynamic_color_tag = "warm_ceiling_lights"
            else:
                dynamic_color_tag = None
            key = (color, texture_key, dynamic_color_tag)
            group = group_lookup.get(key)
            if group is None:
                group = {"color": color, "texture": texture, "parts": [],
                         "dynamic_color_tag": dynamic_color_tag}
                group_lookup[key] = group
                self.material_groups.append(group)
            uv = getattr(visual, "uv", None)
            group["parts"].append((vertices, faces, normals, uv))
        # Compile static geometry once after the window has created an
        # OpenGL context. The pin model is reused ten times per frame.
        self._display_list = 0
        self._material_lists = []
        self._texture_ids = {}

    def _draw_geometry(self):
        for vertices, faces, face_normals in self.parts:
            glBegin(GL_TRIANGLES)
            for face, normal in zip(faces, face_normals):
                glNormal3fv(normal)
                for index in face:
                    glVertex3fv(vertices[index])
            glEnd()

    def _compile_display_list(self):
        display_list = glGenLists(1)
        if not display_list:
            return False
        glNewList(display_list, GL_COMPILE)
        self._draw_geometry()
        glEndList()
        self._display_list = display_list
        return True

    def _upload_texture(self, image):
        if image is None:
            return 0
        key = (image.size, hash(image.tobytes()))
        if key in self._texture_ids:
            return self._texture_ids[key]
        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        rgba = image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, rgba.width, rgba.height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, rgba.tobytes())
        self._texture_ids[key] = texture_id
        return texture_id

    def _compile_material_lists(self):
        if self._material_lists:
            return
        for group in self.material_groups:
            display_list = glGenLists(1)
            if not display_list:
                self._material_lists = []
                return
            glNewList(display_list, GL_COMPILE)
            for vertices, faces, normals, uv in group["parts"]:
                glBegin(GL_TRIANGLES)
                for face, normal in zip(faces, normals):
                    glNormal3fv(normal)
                    for index in face:
                        if uv is not None:
                            glTexCoord2fv(uv[index])
                        glVertex3fv(vertices[index])
                glEnd()
            glEndList()
            self._material_lists.append(display_list)

    def _draw_material_group(self, group):
        for vertices, faces, normals, uv in group["parts"]:
            glBegin(GL_TRIANGLES)
            for face, normal in zip(faces, normals):
                glNormal3fv(normal)
                for index in face:
                    if uv is not None:
                        glTexCoord2fv(uv[index])
                    glVertex3fv(vertices[index])
            glEnd()

    def prepare(self):
        """Build cached geometry after an OpenGL context has been created."""
        if self.use_materials:
            self._compile_material_lists()
            for group in self.material_groups:
                self._upload_texture(group["texture"])
        elif not self._display_list:
            self._compile_display_list()

    def draw(self, color, dynamic_colors=None, exclude_dynamic_tags=()):
        if self.use_materials:
            if not self._material_lists:
                self._compile_material_lists()
            excluded_tags = set(exclude_dynamic_tags)
            for index, group in enumerate(self.material_groups):
                dynamic_tag = group["dynamic_color_tag"]
                if dynamic_tag in excluded_tags:
                    continue
                neon_unlit = bool(dynamic_tag and dynamic_colors
                                  and dynamic_tag in dynamic_colors)
                was_lit = bool(glIsEnabled(GL_LIGHTING)) if neon_unlit else False
                group_color = (dynamic_colors.get(dynamic_tag, group["color"])
                               if dynamic_colors and dynamic_tag else group["color"])
                glColor3f(*group_color)
                emission = ((*group_color, 1.0) if dynamic_tag and dynamic_colors
                            and dynamic_tag in dynamic_colors else (0.0, 0.0, 0.0, 1.0))
                glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, emission)
                if neon_unlit and index < len(self._material_lists):
                    # Treat neon strokes as self-lit, and bias them just ahead
                    # of their wall so depth precision cannot break the lines.
                    glDisable(GL_LIGHTING)
                    glEnable(GL_POLYGON_OFFSET_FILL)
                    glPolygonOffset(-1.0, -1.0)
                if index >= len(self._material_lists):
                    for fallback_group in self.material_groups:
                        fallback_texture = self._upload_texture(fallback_group["texture"])
                        fallback_tag = fallback_group["dynamic_color_tag"]
                        if fallback_tag in excluded_tags:
                            continue
                        fallback_neon = bool(fallback_tag and dynamic_colors
                                             and fallback_tag in dynamic_colors)
                        fallback_was_lit = (bool(glIsEnabled(GL_LIGHTING))
                                            if fallback_neon else False)
                        fallback_color = (dynamic_colors.get(fallback_tag, fallback_group["color"])
                                          if dynamic_colors and fallback_tag
                                          else fallback_group["color"])
                        glColor3f(*fallback_color)
                        fallback_emission = ((*fallback_color, 1.0)
                                             if fallback_tag and dynamic_colors
                                             and fallback_tag in dynamic_colors
                                             else (0.0, 0.0, 0.0, 1.0))
                        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, fallback_emission)
                        if fallback_neon:
                            glDisable(GL_LIGHTING)
                            glEnable(GL_POLYGON_OFFSET_FILL)
                            glPolygonOffset(-1.0, -1.0)
                        if fallback_texture:
                            glEnable(GL_TEXTURE_2D)
                            glBindTexture(GL_TEXTURE_2D, fallback_texture)
                        else:
                            glDisable(GL_TEXTURE_2D)
                        self._draw_material_group(fallback_group)
                        if fallback_neon:
                            glDisable(GL_POLYGON_OFFSET_FILL)
                            if fallback_was_lit:
                                glEnable(GL_LIGHTING)
                    glDisable(GL_TEXTURE_2D)
                    glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, (0.0, 0.0, 0.0, 1.0))
                    return
                texture_id = self._upload_texture(group["texture"])
                if texture_id:
                    glEnable(GL_TEXTURE_2D)
                    glBindTexture(GL_TEXTURE_2D, texture_id)
                else:
                    glDisable(GL_TEXTURE_2D)
                glCallList(self._material_lists[index])
                if neon_unlit:
                    glDisable(GL_POLYGON_OFFSET_FILL)
                    if was_lit:
                        glEnable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, (0.0, 0.0, 0.0, 1.0))
            return
        glColor3f(*color)
        if not self._display_list:
            self._compile_display_list()
        if self._display_list:
            glCallList(self._display_list)
        else:
            # Compatibility fallback for a driver without display lists.
            self._draw_geometry()
