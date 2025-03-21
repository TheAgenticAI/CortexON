import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
import {createKeyFromWebsite} from "@/lib/utils";
import {useAddSecretMutation} from "@/services/vaultApi";
import {Eye, EyeOff, Plus} from "lucide-react";
import {useState} from "react";
import {Button} from "../ui/button";
import {Input} from "../ui/input";
import {Label} from "../ui/label";
const AddCreds = () => {
  const [open, setOpen] = useState(false);

  const [website, setWebsite] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [addSecret, {isLoading}] = useAddSecretMutation();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const websiteKey = createKeyFromWebsite(website);

    // Prepare the data for API
    const secrets = {
      [websiteKey]: JSON.stringify({
        website: website,
        username: username,
        password: password,
      }),
    };

    addSecret({
      namespace: import.meta.env.VITE_APP_VA_NAMESPACE,
      secrets: secrets,
    })
      .unwrap()
      .then(() => {
        setOpen(false);
        setWebsite("");
        setUsername("");
        setPassword("");
      })
      .catch((err) => {
        console.log(err);
      });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" className="gap-2" onClick={() => setOpen(true)}>
        <Plus absoluteStrokeWidth /> Add new Credentials
      </Button>
      <DialogContent className="min-w-[60vw]">
        <DialogTitle>Add New Credentials</DialogTitle>
        <div className="space-y-6 py-4">
          <div className="space-y-2">
            <Label className="text-lg">Website</Label>
            <Input
              type="text"
              placeholder="xyz@abc.com"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
          </div>
          <div className="flex gap-4">
            <div className="space-y-2 w-[50%]">
              <Label className="text-lg">Username</Label>
              <Input
                type="text"
                placeholder="Enter you username for website."
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="space-y-2 w-[50%]">
              <Label className="text-lg">Password</Label>
              <div className="relative hover:cursor-pointer">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password for website."
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
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
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            type="submit"
            onClick={onSubmit}
            disabled={!website || !username || !password}
          >
            {isLoading ? "Adding..." : "Add Credentials"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AddCreds;
