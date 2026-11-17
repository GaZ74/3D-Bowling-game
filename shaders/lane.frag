#version 120
varying vec2 vUV;
varying vec4 vTint;

void main() {
    float grain = 0.5 + 0.5 * sin(vUV.y * 210.0 + sin(vUV.x * 24.0) * 2.0);
    float plank = 0.5 + 0.5 * sin(vUV.x * 32.0);
    float edge = smoothstep(0.0, 0.08, min(vUV.x, 1.0 - vUV.x));
    vec3 darkWood = vec3(0.24, 0.105, 0.045);
    vec3 warmWood = vec3(0.69, 0.39, 0.16);
    vec3 color = mix(darkWood, warmWood, 0.48 + grain * 0.16 + plank * 0.08);
    color *= mix(0.72, 1.0, edge);
    gl_FragColor = vec4(color, 1.0) * vTint;
}
