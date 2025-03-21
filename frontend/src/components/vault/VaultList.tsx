import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {useDeleteSecretMutation} from "@/services/vaultApi";
import {TSecret} from "@/types/vaultTypes";
import {Trash} from "lucide-react";
import {useState} from "react";
import {Button} from "../ui/button";
import {Input} from "../ui/input";
import {Label} from "../ui/label";
import {DeleteAlert} from "./DeleteAlert";

export const VaultList = ({secrets}: {secrets: TSecret[]}) => {
  const [deleteSecret, {isLoading}] = useDeleteSecretMutation();
  const [open, setOpen] = useState(false);

  return (
    <Accordion type="single" collapsible className="space-y-2 pr-3">
      {secrets.map((secret) => (
        <AccordionItem
          value={secret.website}
          className="border-none bg-sidebar text-sidebar-foreground py-1 px-4 rounded-xl"
        >
          <AccordionTrigger>
            <div className="flex flex-row items-center gap-3">
              {secret.website.split("http://")[1]}
              <p className="text-muted-foreground">
                {secret.secrets.length} accounts
              </p>
            </div>
          </AccordionTrigger>
          <AccordionContent className="space-y-4 pl-4 pt-2">
            {secret.secrets.map((secret) => (
              <div className="flex flex-row gap-2 items-end">
                <div className="space-y-2 w-[50%]">
                  <Label>Username</Label>
                  <Input
                    type="text"
                    placeholder="Enter you username for website."
                    value={secret.username}
                    readOnly
                  />
                </div>
                <div className="space-y-2 w-[50%]">
                  <Label>Password</Label>
                  <Input
                    type="password"
                    placeholder="Enter your password for website."
                    value={secret.password}
                    readOnly
                  />
                </div>
                <DeleteAlert
                  trigger={
                    <Button
                      size="icon"
                      variant="destructive"
                      onClick={() => setOpen(true)}
                    >
                      <Trash className="w-4 h-4" />
                    </Button>
                  }
                  onDelete={() => {
                    deleteSecret({
                      secret_key: secret.id,
                      namespace: import.meta.env.VITE_APP_VA_NAMESPACE,
                    })
                      .unwrap()
                      .then(() => {
                        setOpen(false);
                      });
                  }}
                  isLoading={isLoading}
                  open={open}
                  setOpen={setOpen}
                />
              </div>
            ))}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
};
