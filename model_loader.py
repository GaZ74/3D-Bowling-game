import numpy as np
import trimesh
from OpenGL.GL import *


class Model:
    def __init__(self, path, target_size, anchor="center"):
        scene = trimesh.load_scene(path)
        meshes = [
            item for item in scene.dump()
            if isinstance(item, trimesh.Trimesh)
        ]

        if not meshes:
            raise ValueError(f"No mesh geometry found in {path}")

        all_vertices = np.concatenate([mesh.vertices for mesh in meshes])
        low = all_vertices.min(axis=0)
        high = all_vertices.max(axis=0)
        center = (low + high) / 2

        # For a pin, put its base at y=0. The project uses Y as vertical.
        if anchor == "bottom":
            center[1] = low[1]

        largest_dimension = max((high - low).max(), 1e-6)
        scale = target_size / largest_dimension

        self.parts = []
        for mesh in meshes:
            vertices = (mesh.vertices - center) * scale
            self.parts.append(
                (vertices, mesh.faces, mesh.face_normals)
            )
        # Compile static geometry once after the window has created an
        # OpenGL context. The pin model is reused ten times per frame.
        self._display_list = 0

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

    def draw(self, color):
        glColor3f(*color)
        if not self._display_list:
            self._compile_display_list()
        if self._display_list:
            glCallList(self._display_list)
        else:
            # Compatibility fallback for a driver without display lists.
            self._draw_geometry()
