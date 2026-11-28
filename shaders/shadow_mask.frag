#version 120
uniform sampler2D uShadowMap;
uniform vec2 uShadowTexel;
varying vec4 vShadowPosition;

void main() {
    vec3 projected = vShadowPosition.xyz / vShadowPosition.w;
    projected = projected * 0.5 + 0.5;
    if (projected.x < 0.0 || projected.x > 1.0 ||
        projected.y < 0.0 || projected.y > 1.0 ||
        projected.z < 0.0 || projected.z > 1.0) {
        gl_FragColor = vec4(0.0);
        return;
    }
    float shadow = 0.0;
    float compareDepth = projected.z - 0.0025;
    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            float storedDepth = texture2D(
                uShadowMap,
                projected.xy + vec2(float(x), float(y)) * uShadowTexel
            ).r;
            shadow += compareDepth > storedDepth ? 1.0 : 0.0;
        }
    }
    shadow /= 9.0;
    gl_FragColor = vec4(0.0, 0.0, 0.0, shadow * 0.32);
}
