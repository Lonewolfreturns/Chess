import QtQuick
import QtQuick3D

// Holds a reference to a shared geometry so Qt Quick 3D never releases its GPU data
// (a geometry whose last user is deleted is not re-uploaded for later users).
Model {
    property var geo: null
    geometry: geo
    castsShadows: false
    receivesShadows: false
}
