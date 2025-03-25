import {Eye, EyeOff} from "lucide-react";
import {useState} from "react";
import {Input} from "./input";

export const PasswordInput = ({
  password,
  setPassword,
  ...props
}: {
  password: string;
  setPassword?: (password: string) => void;
}) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="relative hover:cursor-pointer">
      <Input
        type={showPassword ? "text" : "password"}
        placeholder="Enter your password for website."
        value={password}
        onChange={(e) => setPassword?.(e.target.value)}
        {...props}
      />
      {showPassword ? (
        <Eye
          className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400"
          onClick={() => setShowPassword(!showPassword)}
        />
      ) : (
        <EyeOff
          className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400"
          onClick={() => setShowPassword(!showPassword)}
        />
      )}
    </div>
  );
};
