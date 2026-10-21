import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.Particles3D

// The 3D battlefield. Game logic lives in Python; this file is the stage.
Item {
    id: root
    width: 1100
    height: 800

    // ---- camera (third-person orbit) --------------------------------
    property real yaw: 0
    property real pitch: 36
    property real distance: 15.5
    property real fov: 40
    property vector3d target: Qt.vector3d(0, 0.2, 0.5)
    property vector3d shake: Qt.vector3d(0, 0, 0)
    property real minPitch: 10
    property real maxPitch: 86

    // ---- look (set from Python) ---------------------------------------
    property string skyUrl: ""
    property string boardUrl: ""
    property string runeUrl: ""
    property string texGlow: ""
    property string texSmoke: ""
    property string texStar: ""
    property string texSnow: ""
    property color frameColor: "#2b2220"
    property color rockColor: "#3a3330"
    property color rockEmissive: "#000000"
    property color accentColor: "#d9e3ee"
    property real accentRough: 0.8
    property color terrainGlowColor: "#ff6a1a"
    property real terrainGlowStrength: 3.0
    property color orbitColor: "#3a3330"
    property real orbitOpacity: 1.0
    property real orbitSpeed: 2.0
    property var terrainRock: null
    property var terrainAccent: null
    property var terrainGlow: null
    property var terrainOrbit: null
    property var terrainLake: null
    property var craters: []
    property color fogColor: "#000000"
    property real fogDensity: 0.0
    property color sunColor: "white"
    property real sunBrightness: 1.4
    property vector3d sunRotation: Qt.vector3d(-50, -35, 0)
    property real probeExposure: 1.0
    property string ambientKind: "embers"
    property bool bloom: true
    property bool shadows: true
    property bool msaa: true
    property bool ambientOn: true
    property real runeGlow: 1.0
    property real darkness: 0.0
    property real timeSec: 0
    property bool inputEnabled: true
    property bool cameraInput: true
    property real baseExposure: 1.0
    property bool vignetteOn: false
    property int tonemap: SceneEnvironment.TonemapModeLinear

    // ---- banner -------------------------------------------------------
    property string bannerTitle: ""
    property string bannerSub: ""
    property color bannerColor: "#ffd27a"
    property real bannerAlpha: 0.0
    property real bannerScale: 1.0
    property real bannerSize: 90

    NumberAnimation on timeSec { from: 0; to: 1000000; duration: 1000000000; loops: Animation.Infinite }

    // ================================================================ 3D
    View3D {
        id: view
        anchors.fill: parent
        camera: cam

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.SkyBox
            lightProbe: Texture { source: root.skyUrl; mappingMode: Texture.LightProbe }
            probeExposure: root.probeExposure * (1.0 - root.darkness * 0.7)
            antialiasingMode: root.msaa ? SceneEnvironment.MSAA : SceneEnvironment.NoAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: root.tonemap
            exposure: root.baseExposure * (1.0 - root.darkness * 0.45)
            glowEnabled: root.bloom
            glowStrength: 1.2
            glowIntensity: 0.8
            glowBloom: 0.2
            glowQualityHigh: true
            vignetteEnabled: root.vignetteOn
            vignetteStrength: 0.15 + root.darkness * 2.5
            vignetteRadius: 0.45
            fog: Fog {
                enabled: root.fogDensity > 0
                color: root.fogColor
                density: root.fogDensity
                depthEnabled: true
                depthNear: 28
                depthFar: 320
                depthCurve: 1.2
            }
        }

        Node {
            id: rig
            position: Qt.vector3d(root.target.x + root.shake.x, root.target.y + root.shake.y,
                                  root.target.z + root.shake.z)
            eulerRotation.y: root.yaw
            Node {
                eulerRotation.x: -root.pitch
                PerspectiveCamera {
                    id: cam
                    z: root.distance
                    fieldOfView: root.fov
                    clipNear: 0.2
                    clipFar: 4000
                }
            }
        }

        DirectionalLight {
            id: sun
            eulerRotation: root.sunRotation
            color: root.sunColor
            brightness: root.sunBrightness * (1.0 - root.darkness * 0.8)
            castsShadow: root.shadows
            shadowMapQuality: Light.ShadowMapQualityVeryHigh
            shadowFactor: 75
            shadowMapFar: 45
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(-25, root.sunRotation.y + 160, 0)
            color: root.terrainGlowColor
            brightness: 0.25 * (1.0 - root.darkness)
        }
        PointLight {
            id: fxLight
            objectName: "fxLight"
            color: "white"
            brightness: 0
            position: Qt.vector3d(0, 2, 0)
            quadraticFade: 0.6
            castsShadow: false
        }
        PointLight {
            id: dangerLight
            objectName: "dangerLight"
            color: "#ff2a2a"
            brightness: 0
            position: Qt.vector3d(0, 1, 0)
            quadraticFade: 1.4
        }

        // ---------------------------------------------------- the board
        Node {
            id: boardRoot
            Model {
                source: "#Cube"
                position: Qt.vector3d(0, -0.38, 0)
                scale: Qt.vector3d(0.099, 0.0076, 0.099)
                castsShadows: true
                receivesShadows: true
                materials: PrincipledMaterial { baseColor: root.frameColor; roughness: 0.82 }
            }
            Model {
                source: "#Cube"
                position: Qt.vector3d(0, -0.83, 0)
                scale: Qt.vector3d(0.094, 0.0016, 0.094)
                materials: PrincipledMaterial { baseColor: "#c99a3e"; metalness: 1.0; roughness: 0.3 }
            }
            Model {
                objectName: "boardTop"
                pickable: true
                source: "#Rectangle"
                eulerRotation.x: -90
                y: 0.002
                scale: Qt.vector3d(0.096, 0.096, 1)
                receivesShadows: true
                materials: PrincipledMaterial {
                    baseColorMap: Texture { source: root.boardUrl; generateMipmaps: true; mipFilter: Texture.Linear }
                    roughness: 0.36
                    clearcoatAmount: 0.25
                    emissiveMap: Texture { source: root.runeUrl }
                    emissiveFactor: Qt.vector3d(root.runeGlow * 2.0, root.runeGlow * 2.0, root.runeGlow * 2.0)
                }
            }
        }

        Node { id: piecesRoot; objectName: "piecesRoot" }
        Node { id: markersRoot; objectName: "markersRoot" }
        Node { id: fxRoot; objectName: "fxRoot" }
        Node { id: keeperRoot; objectName: "keeperRoot"; visible: false }

        // ---------------------------------------------------- location
        Node {
            id: terrainRoot
            Model {
                geometry: root.terrainRock
                visible: root.terrainRock !== null
                receivesShadows: true
                castsShadows: false
                materials: PrincipledMaterial {
                    baseColor: root.rockColor
                    roughness: 0.93
                    emissiveFactor: Qt.vector3d(root.rockEmissive.r, root.rockEmissive.g, root.rockEmissive.b)
                }
            }
            Model {
                geometry: root.terrainAccent
                visible: root.terrainAccent !== null
                receivesShadows: true
                materials: PrincipledMaterial { baseColor: root.accentColor; roughness: root.accentRough }
            }
            Model {
                geometry: root.terrainGlow
                visible: root.terrainGlow !== null
                materials: PrincipledMaterial {
                    baseColor: root.terrainGlowColor
                    lighting: PrincipledMaterial.NoLighting
                    emissiveFactor: Qt.vector3d(root.terrainGlowColor.r * root.terrainGlowStrength,
                                                root.terrainGlowColor.g * root.terrainGlowStrength,
                                                root.terrainGlowColor.b * root.terrainGlowStrength)
                }
            }
            Model {
                geometry: root.terrainLake
                visible: root.terrainLake !== null
                materials: PrincipledMaterial {
                    baseColor: "#1a0602"
                    roughness: 0.6
                    emissiveFactor: Qt.vector3d(0.55, 0.12, 0.02)
                }
            }
            Node {
                eulerRotation.y: root.timeSec * root.orbitSpeed
                Model {
                    geometry: root.terrainOrbit
                    visible: root.terrainOrbit !== null
                    materials: PrincipledMaterial {
                        baseColor: root.orbitColor
                        roughness: 0.95
                        opacity: root.orbitOpacity
                        alphaMode: root.orbitOpacity < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
                    }
                }
            }
        }

        // ---------------------------------------------------- particles
        ParticleSystem3D {
            id: psys
            SpriteParticle3D {
                id: pSpark
                sprite: Texture { source: root.texGlow }
                maxAmount: 2000
                color: "#ffd080"
                colorVariation: Qt.vector4d(0.08, 0.08, 0.08, 0.0)
                billboard: true
                blendMode: SpriteParticle3D.Screen
                fadeInDuration: 0
                fadeOutDuration: 250
            }
            SpriteParticle3D {
                id: pFire
                sprite: Texture { source: root.texGlow }
                maxAmount: 1500
                color: "#ff8a30"
                colorVariation: Qt.vector4d(0.1, 0.1, 0.05, 0.0)
                billboard: true
                blendMode: SpriteParticle3D.Screen
                fadeInDuration: 60
                fadeOutDuration: 350
            }
            SpriteParticle3D {
                id: pSmoke
                sprite: Texture { source: root.texSmoke }
                maxAmount: 1200
                color: "#3a2c28"
                colorVariation: Qt.vector4d(0.05, 0.05, 0.05, 0.1)
                billboard: true
                fadeInDuration: 300
                fadeOutDuration: 900
            }
            SpriteParticle3D {
                id: pMagic
                sprite: Texture { source: root.texStar }
                maxAmount: 1200
                color: "#ffffff"
                colorVariation: Qt.vector4d(0.1, 0.1, 0.1, 0.0)
                billboard: true
                blendMode: SpriteParticle3D.Screen
                fadeInDuration: 100
                fadeOutDuration: 400
            }
            SpriteParticle3D {
                id: pAmbient
                sprite: Texture { source: root.ambientKind === "snow" ? root.texSnow : (root.ambientKind === "clouds" ? root.texSmoke : root.texGlow) }
                maxAmount: 1500
                color: root.ambientKind === "embers" ? "#ff7a2a" : (root.ambientKind === "void" ? "#a46bff"
                       : (root.ambientKind === "snow" ? "#ffffff" : "#55fff2dc"))
                colorVariation: Qt.vector4d(0.1, 0.1, 0.1, 0.2)
                billboard: true
                blendMode: root.ambientKind === "clouds" || root.ambientKind === "snow" ? SpriteParticle3D.SourceOver : SpriteParticle3D.Screen
                fadeInDuration: 800
                fadeOutDuration: 1200
            }
            ModelParticle3D {
                id: pDebris
                maxAmount: 400
                delegate: Component {
                    Model {
                        source: "#Cube"
                        scale: Qt.vector3d(0.0006, 0.0006, 0.0006)
                        materials: PrincipledMaterial { baseColor: "#ffffff"; roughness: 0.4; metalness: 0.3 }
                    }
                }
                color: "#888888"
                fadeOutDuration: 300
            }

            ParticleEmitter3D {
                id: eSpark
                particle: pSpark
                emitRate: 0
                lifeSpan: 800
                lifeSpanVariation: 350
                particleScale: 0.13
                particleEndScale: 0.02
                particleScaleVariation: 0.06
                velocity: VectorDirection3D { id: vSpark; direction: Qt.vector3d(0, 2.5, 0); directionVariation: Qt.vector3d(5, 3.5, 5) }
            }
            ParticleEmitter3D {
                id: eFire
                particle: pFire
                emitRate: 0
                lifeSpan: 700
                lifeSpanVariation: 250
                particleScale: 0.55
                particleEndScale: 0.9
                particleScaleVariation: 0.2
                velocity: VectorDirection3D { id: vFire; direction: Qt.vector3d(0, 1.2, 0); directionVariation: Qt.vector3d(1.6, 1.0, 1.6) }
            }
            ParticleEmitter3D {
                id: eSmoke
                particle: pSmoke
                emitRate: 0
                lifeSpan: 1800
                lifeSpanVariation: 600
                particleScale: 0.6
                particleEndScale: 1.6
                particleScaleVariation: 0.25
                velocity: VectorDirection3D { id: vSmoke; direction: Qt.vector3d(0, 0.7, 0); directionVariation: Qt.vector3d(0.6, 0.3, 0.6) }
            }
            ParticleEmitter3D {
                id: eMagic
                particle: pMagic
                emitRate: 0
                lifeSpan: 1100
                lifeSpanVariation: 400
                particleScale: 0.14
                particleEndScale: 0.0
                particleScaleVariation: 0.06
                velocity: VectorDirection3D { id: vMagic; direction: Qt.vector3d(0, 1.0, 0); directionVariation: Qt.vector3d(1.2, 0.8, 1.2) }
            }
            ParticleEmitter3D {
                id: eDebris
                particle: pDebris
                emitRate: 0
                lifeSpan: 1100
                lifeSpanVariation: 300
                particleScale: 1.0
                particleScaleVariation: 0.6
                particleRotationVariation: Qt.vector3d(180, 180, 180)
                particleRotationVelocityVariation: Qt.vector3d(400, 400, 400)
                velocity: VectorDirection3D { direction: Qt.vector3d(0, 3.5, 0); directionVariation: Qt.vector3d(2.5, 1.5, 2.5) }
            }
            Gravity3D { particles: [pSpark, pDebris]; magnitude: 7.0 }

            // ambient atmosphere around the board
            ParticleEmitter3D {
                particle: pAmbient
                enabled: root.ambientOn
                emitRate: root.ambientKind === "snow" ? 60 : (root.ambientKind === "clouds" ? 6 : 22)
                lifeSpan: root.ambientKind === "clouds" ? 12000 : 7000
                lifeSpanVariation: 2000
                position: Qt.vector3d(0, root.ambientKind === "snow" ? 9 : (root.ambientKind === "clouds" ? -11 : -2), 0)
                shape: ParticleShape3D { type: ParticleShape3D.Cube; extents: Qt.vector3d(root.ambientKind === "clouds" ? 26 : 14, root.ambientKind === "clouds" ? 2 : 4, root.ambientKind === "clouds" ? 26 : 14) }
                particleScale: root.ambientKind === "clouds" ? 6.0 : (root.ambientKind === "snow" ? 0.07 : 0.08)
                particleEndScale: root.ambientKind === "clouds" ? 9.0 : (root.ambientKind === "snow" ? 0.07 : 0.02)
                particleScaleVariation: root.ambientKind === "clouds" ? 2.0 : 0.04
                velocity: VectorDirection3D {
                    direction: root.ambientKind === "snow" ? Qt.vector3d(0.3, -1.4, 0.1)
                               : (root.ambientKind === "clouds" ? Qt.vector3d(0.25, 0.0, 0.1) : Qt.vector3d(0, 0.8, 0))
                    directionVariation: Qt.vector3d(0.4, 0.3, 0.4)
                }
            }
            Repeater3D {
                model: root.ambientOn ? root.craters : []
                delegate: Node {
                    ParticleEmitter3D {
                        system: psys
                        particle: pSmoke
                        position: modelData
                        emitRate: 9
                        lifeSpan: 9000
                        particleScale: 5.0
                        particleEndScale: 16.0
                        shape: ParticleShape3D { type: ParticleShape3D.Sphere; extents: Qt.vector3d(2, 1, 2) }
                        velocity: VectorDirection3D { direction: Qt.vector3d(0.6, 4.0, 0); directionVariation: Qt.vector3d(1, 1, 1) }
                    }
                    ParticleEmitter3D {
                        system: psys
                        particle: pFire
                        position: modelData
                        emitRate: 16
                        lifeSpan: 2200
                        particleScale: 2.2
                        particleEndScale: 0.4
                        shape: ParticleShape3D { type: ParticleShape3D.Sphere; extents: Qt.vector3d(2, 0.5, 2) }
                        velocity: VectorDirection3D { direction: Qt.vector3d(0, 7.0, 0); directionVariation: Qt.vector3d(3, 3, 3) }
                    }
                }
            }
        }
    }

    // ============================================================ API
    // Called from Python through bridge.fx(name, args)
    function burst(kind, x, y, z, count, color, speed, spread, scale) {
        var p = Qt.vector3d(x, y, z)
        if (kind === "spark") {
            pSpark.color = color
            vSpark.direction = Qt.vector3d(0, speed * 0.5, 0)
            vSpark.directionVariation = Qt.vector3d(spread, speed * 0.6, spread)
            eSpark.particleScale = 0.13 * scale
            eSpark.burst(count, 40, p)
        } else if (kind === "fire") {
            pFire.color = color
            vFire.direction = Qt.vector3d(0, speed, 0)
            vFire.directionVariation = Qt.vector3d(spread, speed * 0.5, spread)
            eFire.particleScale = 0.55 * scale
            eFire.particleEndScale = 0.9 * scale
            eFire.burst(count, 80, p)
        } else if (kind === "smoke") {
            pSmoke.color = color
            vSmoke.direction = Qt.vector3d(0, speed, 0)
            vSmoke.directionVariation = Qt.vector3d(spread, speed * 0.4, spread)
            eSmoke.particleScale = 0.6 * scale
            eSmoke.particleEndScale = 1.6 * scale
            eSmoke.burst(count, 120, p)
        } else if (kind === "magic") {
            pMagic.color = color
            vMagic.direction = Qt.vector3d(0, speed, 0)
            vMagic.directionVariation = Qt.vector3d(spread, speed * 0.6, spread)
            eMagic.particleScale = 0.14 * scale
            eMagic.burst(count, 60, p)
        } else if (kind === "debris") {
            pDebris.color = color
            eDebris.burst(count, 30, p)
        }
    }

    function setLight(name, x, y, z, r, g, b, brightness) {
        var l = name === "danger" ? dangerLight : fxLight
        l.position = Qt.vector3d(x, y, z)
        l.color = Qt.rgba(r, g, b, 1)
        l.brightness = brightness
    }

    function spawn(url, parentName, props) {
        var parentNode = parentName === "pieces" ? piecesRoot : (parentName === "markers" ? markersRoot
                         : (parentName === "keeper" ? keeperRoot : fxRoot))
        var c = Qt.createComponent(url)
        if (c.status !== Component.Ready) {
            console.log("spawn failed", url, c.errorString())
            return null
        }
        return c.createObject(parentNode, props)
    }

    function boardHit(mx, my) {
        var res = view.pickAll(mx, my)
        var out = { ok: false, x: 0, z: 0, sq: -1 }
        for (var i = 0; i < res.length; ++i) {
            var o = res[i].objectHit
            if (!o)
                continue
            if (out.sq < 0 && o.objectName === "piece")
                out.sq = o.sq
            if (o.objectName === "boardTop") {
                out.ok = true
                out.x = res[i].scenePosition.x
                out.z = res[i].scenePosition.z
                break
            }
        }
        return out
    }

    Connections {
        target: bridge
        function onFx(name, args) {
            if (name === "burst")
                root.burst.apply(root, args)
            else if (name === "light")
                root.setLight.apply(root, args)
        }
    }

    // ============================================================ input
    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        property real lastX: 0
        property real lastY: 0
        property real pressX: 0
        property real pressY: 0
        property bool orbiting: false
        property bool pieceDrag: false
        property int button: 0

        enabled: root.cameraInput
        onPressed: (ev) => {
            lastX = ev.x; lastY = ev.y; pressX = ev.x; pressY = ev.y
            orbiting = false
            pieceDrag = false
            button = ev.button
            if (!root.inputEnabled)
                return
            var h = root.boardHit(ev.x, ev.y)
            if (ev.button === Qt.LeftButton) {
                if (bridge.pressAt(h.ok ? h.x : 99, h.ok ? h.z : 99, h.sq))
                    pieceDrag = true
            } else if (ev.button === Qt.RightButton) {
                bridge.rightPress(h.ok ? h.x : 99, h.ok ? h.z : 99, h.sq)
            }
        }
        onPositionChanged: (ev) => {
            var dx = ev.x - lastX, dy = ev.y - lastY
            lastX = ev.x; lastY = ev.y
            if (pieceDrag) {
                var h = root.boardHit(ev.x, ev.y)
                if (h.ok)
                    bridge.dragTo(h.x, h.z)
                return
            }
            if (pressed) {
                if (!orbiting && Math.abs(ev.x - pressX) + Math.abs(ev.y - pressY) > 6)
                    orbiting = true
                if (orbiting) {
                    if (button === Qt.MiddleButton) {
                        root.distance = Math.max(7, Math.min(32, root.distance * (1 + dy * 0.004)))
                    } else {
                        root.yaw -= dx * 0.32
                        root.pitch = Math.max(root.minPitch, Math.min(root.maxPitch, root.pitch + dy * 0.25))
                    }
                    bridge.cameraMoved()
                }
                return
            }
            var hh = root.boardHit(ev.x, ev.y)
            bridge.hoverAt(hh.ok ? hh.x : 99, hh.ok ? hh.z : 99, hh.sq)
        }
        onReleased: (ev) => {
            var h = root.boardHit(ev.x, ev.y)
            if (pieceDrag) {
                bridge.releaseAt(h.ok ? h.x : 99, h.ok ? h.z : 99, h.sq)
            } else if (button === Qt.RightButton && !orbiting) {
                bridge.rightRelease(h.ok ? h.x : 99, h.ok ? h.z : 99, h.sq)
            }
            pieceDrag = false
            orbiting = false
        }
        onWheel: (ev) => {
            var k = ev.angleDelta.y > 0 ? 0.9 : 1.1
            root.distance = Math.max(7, Math.min(32, root.distance * k))
            bridge.cameraMoved()
        }
    }

    // ============================================================ overlay
    Item {
        anchors.centerIn: parent
        width: parent.width
        height: 240
        opacity: root.bannerAlpha
        visible: root.bannerAlpha > 0.01
        scale: root.bannerScale
        Rectangle {
            anchors.centerIn: parent
            width: parent.width
            height: root.bannerSub.length > 0 ? 210 : 150
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#00000000" }
                GradientStop { position: 0.2; color: "#c0080412" }
                GradientStop { position: 0.8; color: "#c0080412" }
                GradientStop { position: 1.0; color: "#00000000" }
            }
        }
        Text {
            id: bannerText
            anchors.centerIn: parent
            anchors.verticalCenterOffset: root.bannerSub.length > 0 ? -22 : 0
            text: root.bannerTitle
            color: root.bannerColor
            font.family: "Palatino Linotype"
            font.pixelSize: root.bannerSize
            font.bold: true
            font.letterSpacing: 6
            style: Text.Outline
            styleColor: "#40000000"
        }
        Text {
            anchors.top: bannerText.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.bannerSub
            color: "#f1e9ff"
            font.family: "Palatino Linotype"
            font.pixelSize: Math.max(18, root.bannerSize * 0.28)
            font.bold: true
        }
    }
}
