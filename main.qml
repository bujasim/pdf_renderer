import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window
import QtQuick.Pdf

    ApplicationWindow {
        id: window
        width: 1024
        height: 768
        visible: true
        title: document.title !== "" ? document.title : "PDF Viewer"

    property real zoomStep: 1.25
    property real minZoom: 0.1
    property real maxZoom: 10
    property real zoomSpeed: 0.18
    property real targetScale: 1.0
    property real baseScale: 1.0
    property real previewScaleFactor: 1.0
    property real lastWheelX: 0.0
    property real lastWheelY: 0.0
    property bool zoomInteracting: false
    property bool syncingScale: false

    function clampZoom(scale) {
        return Math.max(minZoom, Math.min(maxZoom, scale))
    }

    function setImmediateScale(scale) {
        zoomInteracting = false
        targetScale = clampZoom(scale)
        previewScaleFactor = 1.0
        applySettledScale(view.width / 2, view.height / 2)
    }

    function applySettledScale(anchorX, anchorY) {
        if (view.currentPage < 0) {
            syncingScale = true
            view.renderScale = targetScale
            syncingScale = false
            baseScale = view.renderScale
            return
        }
        const safeBase = Math.max(0.0001, baseScale)
        const anchorPageX = (view.contentX + anchorX) / safeBase
        const anchorPageY = (view.contentY + anchorY) / safeBase
        const locationX = anchorPageX - (anchorX / targetScale)
        const locationY = anchorPageY - (anchorY / targetScale)
        syncingScale = true
        view.goToLocation(view.currentPage, Qt.point(locationX, locationY), targetScale)
        syncingScale = false
        baseScale = targetScale
    }

    Timer {
        id: settleTimer
        interval: 180
        repeat: false
        onTriggered: {
            zoomInteracting = false
            previewScaleFactor = 1.0
            applySettledScale(lastWheelX, lastWheelY)
        }
    }

    FileDialog {
        id: fileDialog
        title: "Please choose a PDF file"
        nameFilters: ["PDF files (*.pdf)"]
        onAccepted: {
            document.source = selectedFile
            view.scaleToPage(view.width, view.height)
        }
    }

    Dialog {
        id: passwordDialog
        title: "Password"
        standardButtons: Dialog.Ok | Dialog.Cancel
        modal: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: parent
        width: 300

        contentItem: TextField {
            id: passwordField
            placeholderText: "Please provide the password"
            echoMode: TextInput.Password
            width: parent.width
            onAccepted: passwordDialog.accept()
        }

        onOpened: passwordField.forceActiveFocus()
        onAccepted: document.password = passwordField.text
    }

    Dialog {
        id: errorDialog
        title: "Error loading " + document.source
        standardButtons: Dialog.Close
        modal: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: parent
        width: 320
        visible: document.status === PdfDocument.Error

        contentItem: Label {
            text: document.error
            wrapMode: Text.WordWrap
        }
    }

    PdfDocument {
        id: document
        onPasswordRequired: passwordDialog.open()
    }

    menuBar: MenuBar {
        Menu {
            title: "File"
            MenuItem { text: "Open..."; onTriggered: fileDialog.open() }
        }
            Menu {
                title: "View"
            MenuItem { text: "Zoom In"; onTriggered: window.setImmediateScale(view.renderScale * zoomStep) }
            MenuItem { text: "Zoom Out"; onTriggered: window.setImmediateScale(view.renderScale / zoomStep) }
            MenuItem {
                text: "Fit Page"
                onTriggered: {
                    view.scaleToPage(view.width, view.height)
                    window.zoomInteracting = false
                    Qt.callLater(() => window.setImmediateScale(view.renderScale))
                }
            }
            MenuItem {
                text: "Fit Width"
                onTriggered: {
                    view.scaleToWidth(view.width, view.height)
                    window.zoomInteracting = false
                    Qt.callLater(() => window.setImmediateScale(view.renderScale))
                }
            }
                MenuSeparator { }
                MenuItem { text: "Previous Page"; onTriggered: view.back() }
                MenuItem { text: "Next Page"; onTriggered: view.forward() }
            }
        }

        PdfScrollablePageView {
            id: view
            anchors.fill: parent
            document: document
            focus: true

            transform: Scale {
                origin.x: window.lastWheelX
                origin.y: window.lastWheelY
                xScale: window.previewScaleFactor
                yScale: window.previewScaleFactor
            }

            onRenderScaleChanged: {
                if (!window.zoomInteracting && !window.syncingScale) {
                    window.targetScale = view.renderScale
                    window.baseScale = view.renderScale
                }
            }

            WheelHandler {
                target: null
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                acceptedModifiers: Qt.ControlModifier
                onWheel: (event) => {
                    let delta = event.angleDelta.y
                    if (!delta)
                        delta = event.pixelDelta.y
                    if (!delta)
                        return
                    const steps = event.angleDelta.y ? (event.angleDelta.y / 120) : (event.pixelDelta.y / 60)
                    const factor = Math.exp(steps * window.zoomSpeed)
                    if (!window.zoomInteracting)
                        window.baseScale = view.renderScale
                    window.targetScale = window.clampZoom(window.targetScale * factor)
                    const pos = event.position || (event.point ? event.point.position : null)
                    if (pos) {
                        window.lastWheelX = pos.x
                        window.lastWheelY = pos.y
                    } else {
                        window.lastWheelX = view.width / 2
                        window.lastWheelY = view.height / 2
                    }
                    window.previewScaleFactor = window.targetScale / window.baseScale
                    window.zoomInteracting = true
                    settleTimer.restart()
                    event.accepted = true
                }
            }
        }

    footer: ToolBar {
        RowLayout {
            anchors.fill: parent
            Label {
                text: document.status === PdfDocument.Ready
                      ? ("Page " + (view.currentPage + 1) + " / " + document.pageCount + " | Zoom " + view.renderScale.toFixed(2))
                      : ""
                Layout.fillWidth: true
                leftPadding: 10
            }
        }
    }
}
