#version 120
uniform mat4 uCameraToLight;
varying vec4 vShadowPosition;

void main() {
    gl_Position = ftransform();
    vShadowPosition = uCameraToLight * gl_ModelViewMatrix * gl_Vertex;
}
