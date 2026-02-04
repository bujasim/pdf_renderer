import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window

ApplicationWindow {
    id: window
    width: 1024
    height: 768
    visible: true
    title: "MuPDF Tiled Viewer"

    property real zoomStep: 1.15

    FileDialog {
        id: fileDialog
        title: "Please choose a PDF file"
        nameFilters: ["PDF files (*.pdf)"]
        onAccepted: {
            var path = selectedFile.toString();
            if (Qt.platform.os === "windows") {
                path = path.replace(/^(file:\/{3})/, "");
                path = path.replace(/\//g, "\\");
            } else {
                path = path.replace(/^(file:\/{2})/, "");
            }
            pdfController.pdfPath = path;
            pdfController.fitPage();
            pdfController.requestRender();
        }
    }

    menuBar: MenuBar {
        Menu {
            title: "File"
            MenuItem { text: "Open..."; onTriggered: fileDialog.open() }
        }
        Menu {
            title: "View"
            MenuItem { text: "Zoom In"; onTriggered: pdfController.zoomAt(1.25, viewport.width / 2, viewport.height / 2) }
            MenuItem { text: "Zoom Out"; onTriggered: pdfController.zoomAt(1.0 / 1.25, viewport.width / 2, viewport.height / 2) }
            MenuItem { text: "Fit Page"; onTriggered: pdfController.fitPage() }
        }
    }

    Connections {
        target: pdfController
        function onPageChanged() {
            // No-op here; delegates reset on page change
        }
    }

    Item {
        id: viewport
        anchors.fill: parent

        function currentDpr() {
            if (window.screen && window.screen.devicePixelRatio) {
                return window.screen.devicePixelRatio;
            }
            return 1.0;
        }

        onWidthChanged: pdfController.setViewportSize(width, height, currentDpr())
        onHeightChanged: pdfController.setViewportSize(width, height, currentDpr())

        Component.onCompleted: pdfController.setViewportSize(width, height, currentDpr())

        Image {
            id: view
            anchors.fill: parent
            source: "image://pdf_viewport/frame?gen=" + pdfController.frameId
            cache: false
            asynchronous: true
            fillMode: Image.Stretch
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            property real lastX: 0
            property real lastY: 0

            onPressed: (mouse) => {
                lastX = mouse.x;
                lastY = mouse.y;
            }

            onPositionChanged: (mouse) => {
                if (!pressed) return;
                var dx = mouse.x - lastX;
                var dy = mouse.y - lastY;
                pdfController.panBy(dx, dy);
                lastX = mouse.x;
                lastY = mouse.y;
            }
        }

        WheelHandler {
            target: viewport
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: (event) => {
                var factor = event.angleDelta.y > 0 ? zoomStep : (1.0 / zoomStep);
                var sx = (event && event.position) ? event.position.x : (viewport.width / 2);
                var sy = (event && event.position) ? event.position.y : (viewport.height / 2);
                pdfController.zoomAt(factor, sx, sy);
                event.accepted = true;
            }
        }

        PinchHandler {
            target: viewport
            property real lastScale: 1.0

            onActiveScaleChanged: {
                if (!active || !centroid || !centroid.position) return;
                var factor = activeScale / lastScale;
                pdfController.zoomAt(factor, centroid.position.x, centroid.position.y);
                lastScale = activeScale;
            }

            onActiveChanged: {
                if (!active) lastScale = 1.0;
            }
        }
    }

    footer: ToolBar {
        RowLayout {
            anchors.fill: parent
            Label {
                text: "Path: " + pdfController.pdfPath + " | Zoom: " + pdfController.zoomPercent.toFixed(1) + "%"
                Layout.fillWidth: true
                leftPadding: 10
            }
        }
    }
}
