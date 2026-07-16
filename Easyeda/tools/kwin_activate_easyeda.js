const easyedaWindow = workspace.windowList().find((window) => {
    return window.resourceClass === "EasyEDA_Pro";
});

if (easyedaWindow) {
    easyedaWindow.minimized = false;
    workspace.activeWindow = easyedaWindow;
}
