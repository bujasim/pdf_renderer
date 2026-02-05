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
            MenuItem { text: "Zoom In"; onTriggered: view.renderScale *= zoomStep }
            MenuItem { text: "Zoom Out"; onTriggered: view.renderScale /= zoomStep }
            MenuItem { text: "Fit Page"; onTriggered: view.scaleToPage(view.width, view.height) }
            MenuItem { text: "Fit Width"; onTriggered: view.scaleToWidth(view.width, view.height) }
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
                const factor = delta > 0 ? zoomStep : (1 / zoomStep)
                view.renderScale = Math.max(0.1, Math.min(10, view.renderScale * factor))
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
