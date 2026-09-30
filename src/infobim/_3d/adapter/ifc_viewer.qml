import QtQuick
import QtQuick3D
import QtQuick3D.Helpers

Window {
    id: root
    width: 1280
    height: 800
    visible: true
    title: "InfoBIM 3D Viewer"

    required property var geometries
    required property vector3d sceneCenter
    required property real sceneRadius
    required property QtObject picker

    function pickAt(x, y) {
        var result = view.pick(x, y)
        if (!result.objectHit)
            return ""
        var geometry = result.objectHit.geometry
        root.picker.record(geometry.globalId)
        root.title = "InfoBIM 3D Viewer — " + geometry.ifcType + " " + geometry.elementName + " (" + geometry.globalId + ")"
        return geometry.globalId
    }

    View3D {
        id: view
        objectName: "view"
        anchors.fill: parent

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "#000000"
            antialiasingMode: SceneEnvironment.MSAA
        }

        Node {
            id: orbitOrigin
            objectName: "orbitOrigin"
            position: root.sceneCenter
            // Start above and to the side of the model, not level with it.
            eulerRotation: Qt.vector3d(-25, 35, 0)

            PerspectiveCamera {
                id: camera
                objectName: "camera"
                position: Qt.vector3d(0, 0, root.sceneRadius * 2.5)
                clipNear: root.sceneRadius / 1000
                clipFar: root.sceneRadius * 50
            }
        }

        DirectionalLight { eulerRotation.x: -45; eulerRotation.y: 30 }
        DirectionalLight { eulerRotation.x: 45; eulerRotation.y: -150; brightness: 0.5 }

        // IFC is Z-up, Qt Quick 3D is Y-up.
        Node {
            eulerRotation.x: -90

            Repeater3D {
                model: root.geometries
                delegate: Model {
                    required property var modelData
                    geometry: modelData
                    pickable: true
                    materials: PrincipledMaterial {
                        baseColor: "#c8c8c8"
                        metalness: 0.0
                        roughness: 0.8
                        cullMode: Material.NoCulling
                        lighting: modelData.hasNormals ? PrincipledMaterial.FragmentLighting : PrincipledMaterial.NoLighting
                    }
                }
            }
        }
    }

    // Left drag orbits, Ctrl + left drag pans, the wheel zooms, a tap picks.
    OrbitCameraController {
        anchors.fill: parent
        origin: orbitOrigin
        camera: camera
        panEnabled: true

        TapHandler {
            onTapped: (eventPoint) => root.pickAt(eventPoint.position.x, eventPoint.position.y)
        }
    }
}
