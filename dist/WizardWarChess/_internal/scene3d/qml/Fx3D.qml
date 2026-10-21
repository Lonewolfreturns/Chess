import QtQuick
import QtQuick3D

// Generic glowing effect object driven from Python:
//   kind "orb"   - glowing sphere (projectiles, charge-ups)
//   kind "beam"  - cylinder stretched along +Y (rotate/scale from Python)
//   kind "bolt"  - custom geometry (lightning) supplied as `geo`
//   kind "ring"  - torus shockwave (supplied as `geo`)
Node {
    id: fx
    property string kind: "orb"
    property var geo: null
    property color color: "white"
    property real intensity: 4.0
    property real alpha: 1.0

    Model {
        source: fx.kind === "orb" ? "#Sphere" : (fx.kind === "beam" ? "#Cylinder" : "")
        geometry: (fx.kind === "bolt" || fx.kind === "ring") ? fx.geo : null
        castsShadows: false
        receivesShadows: false
        materials: PrincipledMaterial {
            lighting: PrincipledMaterial.NoLighting
            baseColor: fx.color
            emissiveFactor: Qt.vector3d(fx.color.r * fx.intensity, fx.color.g * fx.intensity, fx.color.b * fx.intensity)
            alphaMode: PrincipledMaterial.Blend
            blendMode: PrincipledMaterial.Screen
            opacity: fx.alpha
            cullMode: Material.NoCulling
        }
    }
}
