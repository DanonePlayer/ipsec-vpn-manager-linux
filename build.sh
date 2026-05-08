#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP=vpn-manager
VERSION=1.0.0

echo "==> Preparando ambiente..."
VENV="$DIR/.build-venv"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

if ! pip show pyinstaller &>/dev/null; then
    echo "    Instalando PyInstaller..."
    pip install pyinstaller --quiet
fi

echo "==> Compilando com PyInstaller..."
pyinstaller \
    --onefile \
    --windowed \
    --name "$APP" \
    --add-data "$DIR/config.example.json:." \
    --distpath "$DIR/dist" \
    --workpath "$DIR/dist/build" \
    --specpath "$DIR/dist" \
    "$DIR/vpn-manager.py"

deactivate

BINARY="$DIR/dist/$APP"

# ─── .deb ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Montando pacote .deb..."

DEB_DIR="$DIR/dist/deb"
PKG="$DEB_DIR/${APP}_${VERSION}"

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN"
mkdir -p "$PKG/usr/bin"
mkdir -p "$PKG/usr/share/applications"
mkdir -p "$PKG/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG/usr/share/$APP"

cp "$BINARY" "$PKG/usr/bin/$APP"
chmod +x "$PKG/usr/bin/$APP"

cp "$DIR/icon.png" "$PKG/usr/share/icons/hicolor/256x256/apps/$APP.png"
cp "$DIR/config.example.json" "$PKG/usr/share/$APP/config.example.json"

cat > "$PKG/usr/share/applications/$APP.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=VPN Manager
Comment=Gerenciador de VPN IPsec
Exec=/usr/bin/$APP
Icon=$APP
Terminal=false
Categories=Network;
StartupWMClass=vpn-manager
EOF

cat > "$PKG/DEBIAN/control" << EOF
Package: $APP
Version: $VERSION
Architecture: amd64
Maintainer: $(git config user.name 2>/dev/null || echo "VPN Manager") <$(git config user.email 2>/dev/null || echo "vpn@manager.local")>
Depends: strongswan
Description: Gerenciador de VPN IPsec com interface gráfica
 Conecta e gerencia túneis VPN IPsec/IKEv1 via interface gráfica simples.
EOF

cat > "$PKG/DEBIAN/postinst" << 'EOF'
#!/bin/bash
update-desktop-database /usr/share/applications/ 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor/ 2>/dev/null || true
EOF
chmod +x "$PKG/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$PKG" "$DEB_DIR/${APP}_${VERSION}_amd64.deb"
echo "    .deb gerado: dist/deb/${APP}_${VERSION}_amd64.deb"

# ─── AppImage ─────────────────────────────────────────────────────────────────
echo ""
echo "==> Montando AppImage..."

APPDIR="$DIR/dist/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp "$BINARY" "$APPDIR/usr/bin/$APP"
cp "$DIR/icon.png" "$APPDIR/$APP.png"
cp "$DIR/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP.png"

cat > "$APPDIR/$APP.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=VPN Manager
Comment=Gerenciador de VPN IPsec
Exec=$APP
Icon=$APP
Terminal=false
Categories=Network;
StartupWMClass=vpn-manager
EOF

cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/vpn-manager" "$@"
EOF
chmod +x "$APPDIR/AppRun"

TOOL="$DIR/dist/appimagetool"
if [ ! -f "$TOOL" ]; then
    echo "    Baixando appimagetool..."
    curl -sSL -o "$TOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL"
fi

ARCH=x86_64 "$TOOL" --comp gzip "$APPDIR" "$DIR/dist/VPNManager-${VERSION}-x86_64.AppImage" \
    || APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$TOOL" --comp gzip "$APPDIR" "$DIR/dist/VPNManager-${VERSION}-x86_64.AppImage"
echo "    AppImage gerado: dist/VPNManager-${VERSION}-x86_64.AppImage"

echo ""
echo "✓ Pronto! Arquivos gerados em dist/:"
echo "    ${APP}_${VERSION}_amd64.deb   → Ubuntu/Mint: duplo clique para instalar"
echo "    VPNManager-${VERSION}-x86_64.AppImage → qualquer Linux: chmod +x e duplo clique"
