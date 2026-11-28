#version 120
uniform sampler2D uFloorTexture;
varying vec2 vUV;
varying vec4 vTint;

void main() {
    vec4 floorColor = texture2D(uFloorTexture, vUV);
    float sheen = 0.97 + 0.03 * sin(vUV.y * 1.5);
    gl_FragColor = vec4(floorColor.rgb * sheen, floorColor.a) * vTint;
}
