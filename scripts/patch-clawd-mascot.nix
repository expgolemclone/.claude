# Clawdマスコット非表示パッチ: NixOS overlay
#
# nixpkgs.overlays = [ (import ./patch-clawd-mascot.nix) ];
final: prev: {
  claude-code = prev.claude-code.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      substituteInPlace cli.js \
        --replace-fail 'color:"clawd_body"' 'color:"clawd_background"'
    '';
  });
}
