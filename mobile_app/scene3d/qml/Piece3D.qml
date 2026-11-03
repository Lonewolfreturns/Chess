import QtQuick
import QtQuick3D

// One medieval chess piece. Geometry comes from Python (procedural meshes).
Node {
    id: piece
    property int square: -1
    property bool idle: true
    property var geoBody: null
    property var geoMetal: null
    property var geoCloth: null
    property var geoGlow: null
    property var geoDark: null
    property color bodyColor: "#efe6d2"
    property real bodyMetal: 0.0
    property real bodyRough: 0.3
    property color metalColor: "#e0ac3e"
    property color clothColor: "#2a4fb0"
    property color glowColor: "#7fdcff"
    property color darkColor: "#202020"
    property real glowStrength: 4.0
    property real flash: 0.0
    property real frost: 0.0
    property real fade: 1.0
    property real selectGlow: 0.0
    property real lift: 0.0
    property real bob: 0.0
    property real tilt: 0.0
    property real squash: 1.0
    property string ringTex: ""
    property real pieceScale: 1.12
    scale: Qt.vector3d(pieceScale, pieceScale, pieceScale)

    function frosted(c) { return Qt.tint(c, Qt.rgba(0.72, 0.9, 1.0, piece.frost * 0.85)) }
    function emis(k) {
        var f = piece.flash * 2.2
        return Qt.vector3d(f + piece.frost * 0.10 * k, f + piece.frost * 0.28 * k, f + piece.frost * 0.45 * k)
    }

    SequentialAnimation on bob {
        loops: Animation.Infinite
        running: piece.idle
        NumberAnimation { to: 0.02; duration: 1300 + Math.random() * 900; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0.0; duration: 1300 + Math.random() * 900; easing.type: Easing.InOutSine }
    }

    Node {
        id: figure
        y: piece.lift + piece.bob
        eulerRotation.x: piece.tilt
        scale: Qt.vector3d(1.0 / Math.sqrt(piece.squash), piece.squash, 1.0 / Math.sqrt(piece.squash))

        Model {
            objectName: "piece"
            property int sq: piece.square
            pickable: true
            castsShadows: true
            receivesShadows: true
            geometry: piece.geoBody
            materials: PrincipledMaterial {
                baseColor: piece.frosted(piece.bodyColor)
                metalness: piece.bodyMetal * (1.0 - piece.frost)
                roughness: piece.bodyRough
                clearcoatAmount: 0.4
                clearcoatRoughnessAmount: 0.12
                emissiveFactor: piece.emis(1.0)
                opacity: piece.fade
                alphaMode: piece.fade < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
            }
        }
        Model {
            objectName: "piece"
            property int sq: piece.square
            pickable: true
            castsShadows: true
            receivesShadows: true
            geometry: piece.geoMetal
            materials: PrincipledMaterial {
                baseColor: piece.frosted(piece.metalColor)
                metalness: 1.0 - piece.frost * 0.6
                roughness: 0.28
                emissiveFactor: piece.emis(1.0)
                opacity: piece.fade
                alphaMode: piece.fade < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
            }
        }
        Model {
            objectName: "piece"
            property int sq: piece.square
            pickable: true
            castsShadows: true
            receivesShadows: true
            geometry: piece.geoCloth
            materials: PrincipledMaterial {
                baseColor: piece.frosted(piece.clothColor)
                metalness: 0.0
                roughness: 0.78
                cullMode: Material.NoCulling
                emissiveFactor: piece.emis(1.0)
                opacity: piece.fade
                alphaMode: piece.fade < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
            }
        }
        Model {
            castsShadows: false
            geometry: piece.geoGlow
            materials: PrincipledMaterial {
                baseColor: piece.glowColor
                lighting: PrincipledMaterial.NoLighting
                emissiveFactor: Qt.vector3d(piece.glowColor.r * piece.glowStrength, piece.glowColor.g * piece.glowStrength,
                                            piece.glowColor.b * piece.glowStrength)
                opacity: piece.fade
                alphaMode: piece.fade < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
            }
        }
        Model {
            castsShadows: true
            geometry: piece.geoDark
            materials: PrincipledMaterial {
                baseColor: piece.frosted(piece.darkColor)
                roughness: 0.55
                metalness: 0.2
                emissiveFactor: piece.emis(1.0)
                opacity: piece.fade
                alphaMode: piece.fade < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
            }
        }
    }

    // glowing selection ring on the board
    Node {
        y: 0.015
        visible: piece.selectGlow > 0.01
        NumberAnimation on eulerRotation.y {
            from: 0; to: 360; duration: 5000; loops: Animation.Infinite
            running: piece.selectGlow > 0.01
        }
        Model {
            source: "#Rectangle"
            eulerRotation.x: -90
            scale: Qt.vector3d(0.0092, 0.0092, 1)
            materials: PrincipledMaterial {
                lighting: PrincipledMaterial.NoLighting
                baseColorMap: Texture { source: piece.ringTex }
                baseColor: piece.glowColor
                alphaMode: PrincipledMaterial.Blend
                blendMode: PrincipledMaterial.Screen
                opacity: piece.selectGlow
                emissiveFactor: Qt.vector3d(piece.glowColor.r * 2.0, piece.glowColor.g * 2.0, piece.glowColor.b * 2.0)
            }
        }
    }
}
