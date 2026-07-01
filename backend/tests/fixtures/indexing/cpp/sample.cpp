#include <string>

struct Greeter {
  std::string prefix;

  std::string render(const std::string& name) const {
    return prefix + name;
  }
};
