import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    width: 1024
    height: 768
    visible: true
    title: "MuPDF Tiled Viewer"

    property real zoom: 1.0

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
            requestUpdate();
        }
    }

    menuBar: MenuBar {
        Menu {
            title: "File"
            MenuItem { text: "Open..."; onTriggered: fileDialog.open() }
        }
        Menu {
            title: "View"
            MenuItem { text: "Zoom In"; onTriggered: { zoom *= 1.25; requestUpdate() } }
            MenuItem { text: "Zoom Out"; onTriggered: { zoom /= 1.25; requestUpdate() } }
            MenuItem { text: "Reset Zoom"; onTriggered: { zoom = 1.0; requestUpdate() } }
        }
    }

    function requestUpdate() {
        pdfController.updateViewport(flickable.contentX, flickable.contentY, flickable.width, flickable.height, zoom);
    }

    function applyZoomAt(screenX, screenY, newZoom) {
        var oldZoom = zoom;
        if (Math.abs(newZoom - oldZoom) < 0.0001) return;
        var px = screenX + flickable.contentX;
        var py = screenY + flickable.contentY;
        zoom = newZoom;
        var scale = newZoom / oldZoom;
        flickable.contentX = px * scale - screenX;
        flickable.contentY = py * scale - screenY;
        requestUpdate();
    }

    Connections {
        target: pdfController
        function onPageChanged() {
            // No-op here; delegates reset on page change
        }
    }

    Flickable {
        id: flickable
        anchors.fill: parent
        contentWidth: pdfController.pageWidth * zoom
        contentHeight: pdfController.pageHeight * zoom
        clip: true
        interactive: true

        // Mouse wheel zoom (Ctrl+wheel) and trackpad pinch
        WheelHandler {
            id: wheelZoom
            target: flickable
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            property real zoomMin: 0.1
            property real zoomMax: 8.0
            property real zoomStep: 1.15

            onWheel: (event) => {
                // Ctrl+wheel for zoom; otherwise let Flickable handle scrolling
                if (!event.modifiers || !(event.modifiers & Qt.ControlModifier)) {
                    event.accepted = false;
                    return;
                }
                var factor = event.angleDelta.y > 0 ? zoomStep : (1.0 / zoomStep);
                var newZoom = Math.max(zoomMin, Math.min(zoomMax, zoom * factor));
                var sx = (event && event.position) ? event.position.x : (flickable.width / 2);
                var sy = (event && event.position) ? event.position.y : (flickable.height / 2);
                applyZoomAt(sx, sy, newZoom);
                event.accepted = true;
            }
        }

        PinchHandler {
            target: flickable
            minimumScale: 0.1
            maximumScale: 8.0
            onActiveScaleChanged: {
                if (!active || !centroid || !centroid.position) return;
                var newZoom = Math.max(minimumScale, Math.min(maximumScale, zoom * activeScale));
                applyZoomAt(centroid.position.x, centroid.position.y, newZoom);
            }
        }

        onContentXChanged: updateTimer.restart()
        onContentYChanged: updateTimer.restart()

        // The Tile Grid
        Item {
            width: flickable.contentWidth
            height: flickable.contentHeight

            Repeater {
                model: Math.ceil(flickable.contentWidth / (pdfController.tileWidth)) * 
                       Math.ceil(flickable.contentHeight / (pdfController.tileHeight))
                
                delegate: Image {
                    property int cols: Math.ceil(flickable.contentWidth / (pdfController.tileWidth))
                    property int row: Math.floor(index / cols)
                    property int col: index % cols
                    
                    x: col * pdfController.tileWidth
                    y: row * pdfController.tileHeight
                    width: Math.max(0, Math.min(pdfController.tileWidth, flickable.contentWidth - x))
                    height: Math.max(0, Math.min(pdfController.tileHeight, flickable.contentHeight - y))
                    visible: width > 0 && height > 0
                    
                    fillMode: Image.Stretch
                    asynchronous: true
                    cache: true
                    property string lastKey: ""
                    
                    source: {
                        if (pdfController.pdfPath === "") return "";
                        var bucketZoom = pdfController.getBucketZoom(zoom);
                        var pathId = Qt.md5(pdfController.pdfPath).substring(0, 8);
                        var key = pathId + "_" + pdfController.pageNumber + "_" + bucketZoom.toFixed(4) + "_" + row + "_" + col;
                        if (lastKey === "") return "";
                        return "image://pdf_tiles/" + lastKey;
                    }

                    Connections {
                        target: pdfController
                        function onPageChanged() {
                            lastKey = "";
                        }
                        function onTileReady(key, r, c, z) {
                            var bucketZoom = pdfController.getBucketZoom(zoom);
                            if (r === row && c === col && Math.abs(z - bucketZoom) < 0.001) {
                                lastKey = key;
                            }
                        }
                    }
                }
            }
        }
    }

    Timer {
        id: updateTimer
        interval: 100
        onTriggered: requestUpdate()
    }

    footer: ToolBar {
        RowLayout {
            anchors.fill: parent
            Label {
                text: "Path: " + pdfController.pdfPath + " | Zoom: " + (zoom * 100).toFixed(1) + "%"
                Layout.fillWidth: true
                leftPadding: 10
            }
        }
    }
}
