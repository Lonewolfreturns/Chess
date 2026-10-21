"""Bridge between Python meshes and Qt Quick 3D (QQuick3DGeometry)."""
from __future__ import annotations

import chess
from PyQt6.QtCore import QByteArray, QObject, pyqtSlot
from PyQt6.QtGui import QVector3D
from PyQt6.QtQml import QQmlEngine
from PyQt6.QtQuick3D import QQuick3DGeometry

from . import piece_models, terrain
from .meshes import Mesh

_A = QQuick3DGeometry.Attribute


class MeshGeometry(QQuick3DGeometry):
    def __init__(self, mesh: Mesh | None = None, with_uv: bool = False, parent=None):
        super().__init__(parent)
        if mesh is not None:
            self.set_mesh(mesh, with_uv)

    def set_mesh(self, mesh: Mesh, with_uv: bool = False):
        self.clear()
        if not mesh.pos:
            mesh = Mesh()
            mesh.v((0, 0, 0))
            mesh.v((0, 0, 0))
            mesh.v((0, 0, 0))
            mesh.tri(0, 1, 2)
        vb, ib, stride = mesh.pack(with_uv)
        self.setStride(stride)
        self.setVertexData(QByteArray(vb))
        self.setIndexData(QByteArray(ib))
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(_A.Semantic.PositionSemantic, 0, _A.ComponentType.F32Type)
        self.addAttribute(_A.Semantic.NormalSemantic, 12, _A.ComponentType.F32Type)
        if with_uv:
            self.addAttribute(_A.Semantic.TexCoord0Semantic, 24, _A.ComponentType.F32Type)
        self.addAttribute(_A.Semantic.IndexSemantic, 0, _A.ComponentType.U32Type)
        lo, hi = mesh.bounds()
        self.setBounds(QVector3D(*lo), QVector3D(*hi))
        self.update()


def _keep(obj: QObject) -> QObject:
    QQmlEngine.setObjectOwnership(obj, QQmlEngine.ObjectOwnership.CppOwnership)
    return obj


class GeometryLibrary(QObject):
    """Holds one shared geometry per piece part and per terrain part."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pieces: dict[tuple, MeshGeometry] = {}
        self._terrain: dict[str, dict] = {}

    def piece(self, piece_type: int, part: str) -> MeshGeometry:
        key = (piece_type, part)
        if key not in self._pieces:
            mesh = piece_models.piece_parts(piece_type)[part]
            self._pieces[key] = _keep(MeshGeometry(mesh))
        return self._pieces[key]

    def piece_set(self, piece_type: int) -> dict:
        return {part: self.piece(piece_type, part) for part in piece_models.PARTS}

    def terrain(self, key: str) -> dict:
        if key not in self._terrain:
            parts = terrain.build(key)
            geo = {name: _keep(MeshGeometry(parts[name]))
                   for name in ("rock", "accent", "glow", "orbit", "lake")}
            geo["craters"] = parts["craters"]
            self._terrain[key] = geo
        return self._terrain[key]

    @pyqtSlot(int, str, result=QObject)
    def get(self, piece_type: int, part: str) -> QObject:
        return self.piece(piece_type, part)
