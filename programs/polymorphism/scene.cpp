// The threepp code in the lesson film "Polymorphism" (films/polymorphism_rules.py). The film
// shows the lines between each "// [name]" and its "// [end]".

#include <threepp/threepp.hpp>

#include <iostream>

using namespace threepp;

int main() {
    auto scene = Scene::create();
    auto geometry = BoxGeometry::create();
    auto material = MeshStandardMaterial::create();

    // [add]
    auto box = Mesh::create(geometry, material);
    auto lamp = PointLight::create();
    auto rig = Group::create();

    scene->add(box);
    scene->add(lamp);
    scene->add(rig);
    // [end]

    // [loop]
    for (Object3D* child : scene->children) {
        std::cout << child->type() << "\n";
    }
    // [end]

    auto sphere = SphereGeometry::create();
    auto shiny = MeshPhongMaterial::create();

    // [swap]
    auto mesh = Mesh::create(geometry, material);

    mesh->setGeometry(sphere);    // a new shape
    mesh->setMaterial(shiny);     // a new look
    // [end]

    std::cout << (mesh->geometry() == sphere && mesh->material() == shiny ? "swapped" : "not swapped") << "\n";
}
