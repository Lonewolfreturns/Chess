import QtQuick
import QtQuick3D

// A glowing textured quad lying on the board (move dots, rings, magic circles...).
Node {
    id: m
    property string tex: ""
    property color color: "white"
    property real alpha: 1.0
    property real size: 1.0          // in board squares
    property real stretch: 1.0       // length multiplier (arrows)
    property real spin: 0.0          // degrees per second
    property real pulse: 0.0         // 0..1
    property real glow: 1.5
    property real t: 0.0
    property real angle: 0.0

    NumberAnimation on t { from: 0; to: 3600; duration: 3600000; loops: Animation.Infinite }

    eulerRotation.y: m.angle + m.t * m.spin

    Model {
        source: "#Rectangle"
        eulerRotation.x: -90
        position: Qt.vector3d(0, 0, -(m.stretch - 1.0) * m.size * 0.5)
        scale: Qt.vector3d(m.size * 0.01 * (1.0 + m.pulse * 0.07 * Math.sin(m.t * 5.0)),
                           m.size * 0.01 * m.stretch, 1)
        castsShadows: false
        receivesShadows: false
        materials: PrincipledMaterial {
            lighting: PrincipledMaterial.NoLighting
            baseColorMap: Texture { source: m.tex }
            baseColor: m.color
            alphaMode: PrincipledMaterial.Blend
            blendMode: PrincipledMaterial.Screen
            cullMode: Material.NoCulling
            opacity: m.alpha * (1.0 - m.pulse * 0.35 + m.pulse * 0.35 * Math.sin(m.t * 5.0))
            emissiveFactor: Qt.vector3d(m.color.r * m.glow, m.color.g * m.glow, m.color.b * m.glow)
        }
    }
}
