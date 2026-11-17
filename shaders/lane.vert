#version 120
varying vec2 vUV;
varying vec4 vTint;

void main() {
    gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
    vUV = gl_MultiTexCoord0.xy;
    vTint = gl_Color;
}
