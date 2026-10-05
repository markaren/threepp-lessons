// The Rectangle and the Square in the lesson film "Polymorphism" (films/polymorphism_rules.py):
// a Square that inherits from Rectangle compiles, and breaks the code written for Rectangle.
// The film shows the lines between each "// [name]" and its "// [end]".

#include <iostream>

class Rectangle {
public:
    virtual ~Rectangle() = default;

    virtual void setWidth(double w) { width_ = w; }
    virtual void setHeight(double h) { height_ = h; }

    double width() const { return width_; }
    double height() const { return height_; }

private:
    double width_ = 1;
    double height_ = 1;
};

// [square]
class Square : public Rectangle {
public:
    void setWidth(double w) override {
        Rectangle::setWidth(w);
        Rectangle::setHeight(w);    // sides stay equal
    }
    void setHeight(double h) override {
        Rectangle::setWidth(h);
        Rectangle::setHeight(h);
    }
};
// [end]

// [resize]
void resize(Rectangle& r, double w, double h) {
    r.setWidth(w);
    r.setHeight(h);
}
// [end]

void report(const char* name, const Rectangle& r, double w, double h) {
    const bool asAsked = r.width() == w && r.height() == h;
    std::cout << name << ": asked for " << w << " x " << h << ", got " << r.width() << " x " << r.height()
              << (asAsked ? "" : ", not what the caller asked for") << "\n";
}

int main() {
    const double w = 2, h = 0.5;

    Rectangle rectangle;
    resize(rectangle, w, h);
    report("Rectangle", rectangle, w, h);

    Square square;
    resize(square, w, h);
    report("Square", square, w, h);
}
